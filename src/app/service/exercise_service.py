import os
import io
import json
import mimetypes
import hashlib
import asyncio
import re
import subprocess
from datetime import datetime
from typing import Optional, Tuple,Dict,Any,List

import uuid
import psycopg2
import requests
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field,validator
from PIL import Image
import random
from app.utils.util import to_pinyin_sentence,segment_sentence


DATABASE_URL = os.getenv("DATABASE_URL")
MEDIA_ROOT = os.getenv("MEDIA_ROOT", "/data/media")
MEDIA_PUBLIC_BASE = os.getenv("MEDIA_PUBLIC_BASE", "/media")
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
APP_ID=os.getenv("APP_ID","")

HSK_LEVEL_DESCRIPTIONS = {
    1: "基础生活交流词汇与简单句",
    2: "常见场景词汇与基本语法",
    3: "一般话题表达，句式略复杂",
    4: "较复杂句式与更广泛话题",
    5: "较高难度词汇与长句表达",
    6: "高级表达与复杂文本理解"
}

TEXT_TYPE_INSTRUCTIONS = {
    "一句话": "生成一个简单、清晰、可视觉化的一句话陈述",
    "两句话": "生成两句相关的简短陈述，便于视觉化",
    "三句话": "生成三句简短且连贯的陈述"
}


def _sha256(b: bytes) -> str:
    h = hashlib.sha256()
    h.update(b)
    return h.hexdigest()

def _date_parts():
    d = datetime.utcnow()
    return d.strftime("%Y"), d.strftime("%m"), d.strftime("%d")

def _ensure_dir(path: str):
    os.makedirs(path, exist_ok=True)

def _guess_ext(mime_type: str, fallback: str) -> str:
    ext = mimetypes.guess_extension(mime_type or "") or fallback
    return {".jpe": ".jpg"}.get(ext, ext)

def _db():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL 未配置")
    return psycopg2.connect(DATABASE_URL)

def _ffprobe_duration_ms(abs_path: str) -> Optional[int]:
    try:
        out = subprocess.check_output([
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", abs_path
        ], stderr=subprocess.DEVNULL)
        dur = float(out.decode().strip())
        return int(dur * 1000)
    except Exception:
        return None

def save_image_asset(cur, data: bytes, mime_type: str) -> str:
    """
    将图片字节码保存到文件系统, 并在media_assets表中创建记录。
    
    Args:
        cur: 数据库游标对象。
        data: 图片的二进制数据。
        mime_type: 图片的MIME类型。

    Returns:
        新创建的媒体资产在数据库中的UUID。
    """
    # 1. 保留原有的文件保存逻辑
    sha = _sha256(data)
    y, m, d = _date_parts()
    prefix = sha[:2]
    ext = _guess_ext(mime_type, ".jpg")
    # 注意：我们存储的是相对路径，这与我们的方案B设计一致
    rel_path = f"images/{y}/{m}/{d}/{prefix}/{sha}{ext}"
    abs_path = os.path.join(MEDIA_ROOT, rel_path)
    _ensure_dir(os.path.dirname(abs_path))
    
    img = Image.open(io.BytesIO(data))
    w, h = img.size
    with open(abs_path, "wb") as f:
        f.write(data)

    # 2. 【新增】将元数据存入数据库
    # 使用 ON CONFLICT 可以在文件已存在时避免重复插入和报错，保证幂等性。
    sql = """
        INSERT INTO content_new.media_assets (file_url, file_type, mime_type, description)
        VALUES (%s, 'image', %s, %s)
        ON CONFLICT (file_url) DO UPDATE SET updated_at = NOW()
        RETURNING id;
    """
    description = f"Image asset, SHA256: {sha}, Dimensions: {w}x{h}"
    cur.execute(sql, (rel_path, mime_type, description))
    media_asset_id = cur.fetchone()[0]

    # 3. 【修改】返回数据库中的ID
    return media_asset_id


def save_audio_asset(cur, data: bytes, mime_type: str) -> str:
    """
    将音频字节码保存到文件系统, 并在media_assets表中创建记录。

    Args:
        cur: 数据库游标对象。
        data: 音频的二进制数据。
        mime_type: 音频的MIME类型。

    Returns:
        新创建的媒体资产在数据库中的UUID。
    """
    # 1. 保留原有的文件保存逻辑
    sha = _sha256(data)
    y, m, d = _date_parts()
    prefix = sha[:2]
    ext = _guess_ext(mime_type, ".mp3")
    rel_path = f"audios/{y}/{m}/{d}/{prefix}/{sha}{ext}"
    abs_path = os.path.join(MEDIA_ROOT, rel_path)
    _ensure_dir(os.path.dirname(abs_path))
    with open(abs_path, "wb") as f:
        f.write(data)

    # 2. 【新增】将元数据存入数据库
    sql = """
        INSERT INTO content_new.media_assets (file_url, file_type, mime_type, description)
        VALUES (%s, 'audio', %s, %s)
        ON CONFLICT (file_url) DO UPDATE SET updated_at = NOW()
        RETURNING id;
    """
    description = f"Audio asset, SHA256: {sha}"
    cur.execute(sql, (rel_path, mime_type, description))
    media_asset_id = cur.fetchone()[0]

    # 3. 【修改】返回数据库中的ID
    return media_asset_id


def generate_from_llm(prompt: str) -> str:
    url = f"https://dashscope.aliyuncs.com/api/v1/apps/{APP_ID}/completion"
    headers = {
        "Authorization": f"Bearer {LLM_API_KEY}",
        "Content-Type": "application/json"
    }
    data = {
        "input": { "prompt": prompt },
        "parameters": {},
        "debug": {}
    }
    try:
        response = requests.post(url, headers=headers, data=json.dumps(data))
        response.raise_for_status()
        result = response.json()
        if 'output' in result and 'text' in result['output']:
            return result['output']['text']
        else:
            return "API响应格式不正确，无法提取文本。"
    except requests.exceptions.RequestException as e:
        print(f"请求失败: {e}")
        return "发生错误，无法生成文本。"
    except json.JSONDecodeError:
        print("API响应不是有效的JSON格式。")
        return "发生错误，无法解析API响应。"

def generate_voice(text: str) -> str:
    if not LLM_API_KEY:
        raise ValueError("请设置环境变量 DASHSCOPE_API_KEY")
    url = 'https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation' 
    headers = {
        "Authorization": f"Bearer {LLM_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": "qwen-tts",
        "input": { "text": text, "voice":"Chelsie" }
    }
    try:
        response = requests.post(url, headers=headers, data=json.dumps(payload))
        response.raise_for_status()
        result=response.json()
        audio_url = result.get('output', {}).get('audio', {}).get('url')
        if not audio_url:
            raise RuntimeError("TTS 响应成功，但未找到音频 URL")
        return audio_url
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"API 请求失败: {e}")

def url_without_course(url: Optional[str]) -> Optional[str]:
    return url

def generate_image(prompt: str, negative: str):
    headers = {
        "Authorization": f"Bearer {LLM_API_KEY}",
        "Content-Type": "application/json",
        "X-DashScope-Async": "enable"
    }
    payload = {
        "model": "wanx2.1-t2i-turbo",
        "input": {
            "prompt": prompt,
            "negative_prompt": negative
        },
        "parameters": {
            "size": "1024*1024",
            "n": 1
        }
    }
    try:
        response = requests.post("https://dashscope.aliyuncs.com/api/v1/services/aigc/text2image/image-synthesis", headers=headers, data=json.dumps(payload))
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"提交文生图任务失败: {e}")

def get_text_to_image_task_status(task_id: str):
    headers = {
        "Authorization": f"Bearer {LLM_API_KEY}",
        "Content-Type": "application/json",
    }
    status_url = f"https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}"
    try:
        response = requests.get(status_url, headers=headers)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"查询任务状态失败: {e}")

async def _poll_image_task(task_id: str, max_try: int = 20, interval_s: float = 1.5) -> Optional[str]:
    """轮询文生图任务直至拿到图片URL；失败/超时返回 None"""
    for _ in range(max_try):
        status = get_text_to_image_task_status(task_id)
        out = status.get("output") or {}
        if out.get("task_status") == "SUCCEEDED":
            return (out.get("results") or [{}])[0].get("url")
        if out.get("task_status") == "FAILED":
            return None
        await asyncio.sleep(interval_s)
    return None


class GenerateReq(BaseModel):
    keyword: str
    hskLevel: int = Field(..., ge=1, le=6)
    isCorrect: bool = True
    textType: str = "一句话"
    lang: str = "zh-CN"
    difficulty: int = Field(2, ge=1, le=5)
    seed: Optional[int] = None

class ListenImageTfResp(BaseModel):
    exercise_id: str
    hsk_level: int
    difficulty: int
    metadata: Dict[str, Any]
    assets: Dict[str, str]

async def create_listen_image_tf_exercise(cur, req: GenerateReq) -> Dict[str, Any]:
    """
    创建一道“听录音,看图判断”题目，并将所有相关数据存入新数据库。
    这是核心业务逻辑，与Web框架无关。

    Args:
        cur: 数据库游标对象。
        req: API请求体，包含keyword, hskLevel等。

    Returns:
        一个字典，包含了新创建的题目的完整信息。
    """
    # === 第1步: 生成核心文本 ===
    hskExplain = HSK_LEVEL_DESCRIPTIONS.get(req.hskLevel, "无特定描述")
    textTypeExplain = TEXT_TYPE_INSTRUCTIONS.get(req.textType, "生成一个简单的句子")
    
    RIGHT_PROMPT_TEMPLATE = f"""
作为一名顶尖的中文教学内容（CSL）设计师，请为“看图判断”题型创作一段高质量的中文文本。
- 核心词汇: 文本必须围绕 `{req.keyword}` 展开。
- 场景要求: 文本必须描述一个清晰、具体、可以用图像轻松表现的场景或动作。
- 目标等级: HSK {req.hskLevel} ({hskExplain})
- 指定形式: {textTypeExplain}
- 输出格式: 请直接输出最终生成的文本，不要包含任何标签。
""".strip()
    listening_text = generate_from_llm(RIGHT_PROMPT_TEMPLATE).strip()
    if not listening_text:
        raise ValueError("AI生成听力文本失败")

    # === 第2步: 生成并保存音频资产 ===
    audio_temp_url = generate_voice(listening_text)
    audio_resp = requests.get(audio_temp_url, timeout=30)
    audio_resp.raise_for_status()
    audio_bytes = audio_resp.content
    audio_mime = audio_resp.headers.get("Content-Type", "audio/mpeg",).split(";")[0]
    
    # 【调用新函数】传入游标，只返回asset_id
    audio_asset_id = save_audio_asset(cur, audio_bytes, audio_mime)
    

    # === 第3步: 生成并保存图片资产 ===
    image_description_text = ""
    if req.isCorrect:
        image_description_text = listening_text
    else:
        WRONG_PROMPT_TEMPLATE = f"""
作为一名严谨的中文试题设计师，你的任务是创作一个与原始句子【相似度极低】的全新句子，用作“看图判断”题的干扰项。
- 原始句子 (HSK {req.hskLevel} 水平): "{listening_text}"
- 核心生成要求: 1. 主题和场景必须完全不同; 2. 严禁使用关键词; 3. 难度和结构对等; 4. 必须可被清晰地转换成一张图片。
- 输出要求: 只输出新句子，不要解释。
""".strip()
        wrong_text = generate_from_llm(WRONG_PROMPT_TEMPLATE).strip()
        if not wrong_text:
            raise ValueError("AI生成干扰项文本失败")
        image_description_text = wrong_text

    image_prompt = f'请根据以下描述生成一张清晰、写实的图片，画面中不要出现任何文字： "{image_description_text}"'
    init = generate_image(image_prompt, "文字, 丑陋, 模糊")
    task_id = init.get("output", {}).get("task_id")
    if not task_id:
        raise ValueError("文生图任务未返回 task_id")

    image_url = None
    for _ in range(20): # 轮询获取图片URL
        status = get_text_to_image_task_status(task_id)
        task_status = status.get("output", {}).get("task_status")
        if task_status == "SUCCEEDED":
            image_url = status.get("output", {}).get("results", [{}])[0].get("url")
            break
        elif task_status == "FAILED":
            raise ValueError("文生图任务失败")
        await asyncio.sleep(1.5)
    
    if not image_url:
        raise ValueError("轮询超时，未获取到图片URL")

    img_resp = requests.get(image_url, timeout=60)
    img_resp.raise_for_status()
    img_bytes = img_resp.content
    img_mime = img_resp.headers.get("Content-Type", "image/jpeg").split(";")[0]
    
    # 【调用新函数】传入游标，只返回asset_id
    image_asset_id = save_image_asset(cur, img_bytes, img_mime)
    

    # === 第4步: 组装数据并写入新数据库 ===
    
    # 4.1 查询外键ID
    cur.execute("SELECT id FROM content_new.words WHERE characters = %s;", (req.keyword,))
    word_id_result = cur.fetchone()
    word_id = word_id_result[0] if word_id_result else None
    if not word_id:
        raise ValueError(f"词库中不存在词语: {req.keyword}")

    exercise_type_name = "LISTEN_IMAGE_TRUE_FALSE" 
    cur.execute("SELECT id FROM content_new.exercise_types WHERE name = %s;", (exercise_type_name,))
    exercise_type_id_result = cur.fetchone()
    exercise_type_id = exercise_type_id_result[0] if exercise_type_id_result else None
    if not exercise_type_id:
        raise ValueError(f"题型库中不存在题型: {exercise_type_name}")

    # 4.2 定义 metadata JSON 对象
    metadata = {
        "listening_text": listening_text,
        "correct_answer": req.isCorrect  # 直接存储布尔值
    }

    # 4.3 插入到 exercises 表
    exercise_id = str(uuid.uuid4())
    cur.execute(
        """
        INSERT INTO content_new.exercises 
        (id, word_id, exercise_type_id, prompt, metadata, difficulty_level)
        VALUES (%s, %s, %s, %s, %s, %s);
        """,
        (exercise_id, word_id, exercise_type_id, "请听录音，再看图片，判断陈述是否正确。", json.dumps(metadata), req.difficulty)
    )

    # 4.4 关联媒体到 exercise_media_assets 表
    cur.execute(
        """
        INSERT INTO content_new.exercise_media_assets (exercise_id, media_asset_id, usage_role)
        VALUES (%s, %s, 'prompt_audio');
        """,
        (exercise_id, audio_asset_id)
    )
    cur.execute(
        """
        INSERT INTO content_new.exercise_media_assets (exercise_id, media_asset_id, usage_role)
        VALUES (%s, %s, 'stem_image');
        """,
        (exercise_id, image_asset_id)
    )

    # === 第5步: 返回创建好的题目ID和相关信息 ===
    return {
        "exercise_id": exercise_id,
        "hsk_level": req.hskLevel,
        "difficulty": req.difficulty,
        "metadata": metadata,
        "word_id": word_id,
        "exercise_type_id": exercise_type_id,
        "assets": {
            "prompt_audio_id": audio_asset_id,
            "stem_image_id": image_asset_id
        }
    }

class MCReq(BaseModel):
    correctKeyword: str
    hskLevel: int = Field(..., ge=1, le=6)
    textType: str = "一句话"
    lang: str = "zh-CN"
    difficulty: int = Field(2, ge=1, le=5)

class MCResp(BaseModel):
    # 注意：这个模型现在只用于路由层的响应类型提示，
    # service函数本身可以返回一个更简单的字典
    exercise_id: str
    question_type: str
    hsk_level: int
    listening_text: str
    audio_url: str # 这里应该是 asset_id
    options: Dict[str, Dict[str, Any]]
    correct_answer: str

async def create_listen_image_mc_exercise(cur, req: MCReq) -> Dict[str, Any]:

    # === 第1步: 生成核心听力文本 ===
    hskExplain = HSK_LEVEL_DESCRIPTIONS.get(req.hskLevel, "无特定描述")
    textTypeExplain = TEXT_TYPE_INSTRUCTIONS.get(req.textType, "生成一个单一、完整的句子。")
    RIGHT_PROMPT_TEMPLATE = f"""
作为一名顶尖的中文教学内容（CSL）设计师，请为“听录音，看图选择”题型创作一段高质量的中文听力文本。
- 核心词汇: 文本必须围绕 `{req.correctKeyword}` 展开。
- 场景要求: 文本必须描述一个清晰、具体、单一、可以用图像轻松表现的场景或动作。
- 目标等级: HSK {req.hskLevel} ({hskExplain})
- 指定形式: {req.textType} ({textTypeExplain})
- 输出格式: 只输出最终文本，不要任何解释或标签。
""".strip()
    listening_text = generate_from_llm(RIGHT_PROMPT_TEMPLATE).strip()
    if not listening_text:
        raise ValueError("AI生成听力文本失败")

    # === 第2步: 生成并保存音频资产 ===
    audio_temp_url = generate_voice(listening_text)
    audio_resp = requests.get(audio_temp_url, timeout=30)
    audio_resp.raise_for_status()
    audio_bytes = audio_resp.content
    audio_mime = audio_resp.headers.get("Content-Type", "audio/mpeg").split(";")[0]
    audio_asset_id = save_audio_asset(cur, audio_bytes, audio_mime)

    # === 第3步: 生成干扰关键词 ===
    distractor_prompt = f'为中文词汇“{req.correctKeyword}”(HSK {req.hskLevel})生成2个同范畴、高相关的干扰词，用于选择题。要求仅输出JSON数组，如：["干扰词1", "干扰词2"]'
    ds_raw = generate_from_llm(distractor_prompt).strip()
    try:
        distractors = json.loads(ds_raw)
        if not isinstance(distractors, list) or len(distractors) < 2:
            raise ValueError("干扰词格式不是包含至少2个元素的数组")
    except (json.JSONDecodeError, ValueError) as e:
        raise ValueError(f"AI生成干扰词格式错误: {e}")

    # === 第4步: 准备并并行生成图片资产 ===
    options_keywords = [req.correctKeyword] + distractors[:2]
    random.shuffle(options_keywords)
    correct_answer_label = chr(ord('A') + options_keywords.index(req.correctKeyword))

    async def _generate_and_save_image(keyword: str) -> str:
        """根据关键词生成并保存单张图片，返回其 asset_id"""
        if keyword == req.correctKeyword:
            prompt = f'请根据以下描述生成一张清晰、写实的图片，画面中不要出现任何文字： "{listening_text}"'
        else:
            prompt = f'一张关于“{keyword}”的高质量照片，主体清晰，背景简单，不要有任何文字。'
        
        init_resp = generate_image(prompt, "文字, 字母, 丑陋, 模糊, 低质量")
        task_id = (init_resp.get("output") or {}).get("task_id")
        if not task_id:
            raise ValueError(f"文生图任务未能启动(keyword: {keyword})")
        
        image_url = await _poll_image_task(task_id)
        if not image_url:
            raise ValueError(f"文生图任务失败或超时(keyword: {keyword})")

        img_resp = requests.get(image_url, timeout=60)
        img_resp.raise_for_status()
        img_bytes = img_resp.content
        img_mime = img_resp.headers.get("Content-Type", "image/jpeg").split(";")[0]
        return save_image_asset(cur, img_bytes, img_mime)

    # 并行执行所有图片生成任务
    image_tasks = [_generate_and_save_image(kw) for kw in options_keywords]
    image_asset_ids = await asyncio.gather(*image_tasks)

    options_data = []
    for i, keyword in enumerate(options_keywords):
        options_data.append({
            "label": chr(ord('A') + i),
            "keyword": keyword,
            "image_asset_id": image_asset_ids[i]
        })

    cur.execute("SELECT id FROM content_new.words WHERE characters = %s;", (req.correctKeyword,))
    word_id = (cur.fetchone() or [None])[0]
    if not word_id:
        raise ValueError(f"词库中不存在词语: {req.correctKeyword}")

    # 注意: 数据库中必须预先存在名为 'LISTEN_IMAGE_MC' 的题型
    exercise_type_name = "LISTEN_IMAGE_MC"
    cur.execute("SELECT id FROM content_new.exercise_types WHERE name = %s;", (exercise_type_name,))
    exercise_type_id = (cur.fetchone() or [None])[0]
    if not exercise_type_id:
        raise ValueError(f"题型库中不存在题型: {exercise_type_name}")

    # 5.2 定义 metadata JSON 对象
    metadata = {
        "listening_text": listening_text,
        "options": options_data,
        "correct_answer": correct_answer_label
    }

    # 5.3 插入到 exercises 表
    exercise_id = str(uuid.uuid4())
    cur.execute(
        """
        INSERT INTO content_new.exercises 
        (id, word_id, exercise_type_id, prompt, metadata, difficulty_level)
        VALUES (%s, %s, %s, %s, %s, %s);
        """,
        (exercise_id, word_id, exercise_type_id, "请听录音，然后选择正确的图片。", json.dumps(metadata), req.difficulty)
    )

    # 5.4 关联所有媒体资产
    # 关联音频
    cur.execute(
        """
        INSERT INTO content_new.exercise_media_assets (exercise_id, media_asset_id, usage_role)
        VALUES (%s, %s, 'prompt_audio');
        """,
        (exercise_id, audio_asset_id)
    )
    # 关联选项图片
    for option in options_data:
        cur.execute(
            """
            INSERT INTO content_new.exercise_media_assets (exercise_id, media_asset_id, usage_role)
            VALUES (%s, %s, %s);
            """,
            (exercise_id, option["image_asset_id"], f'option_image_{option["label"]}')
        )

    all_asset_ids = [audio_asset_id] + image_asset_ids
    cur.execute("SELECT id, file_url FROM content_new.media_assets WHERE id = ANY(%s::uuid[]);", (all_asset_ids,))
    asset_urls = {str(row[0]): f"{MEDIA_PUBLIC_BASE}/{row[1]}" for row in cur.fetchall()}
    
    response_options = {
        opt["label"]: {
            "keyword": opt["keyword"],
            "image_url": asset_urls.get(opt["image_asset_id"])
        } for opt in options_data
    }

    return {
        "exercise_id": exercise_id,
        "question_type": "听录音·看图选择（单选）",
        "hsk_level": req.hskLevel,
        "listening_text": listening_text,
        "audio_url": asset_urls.get(audio_asset_id),
        "options": response_options,
        "correct_answer": correct_answer_label,
    }
class MatchReq(BaseModel):
    """听力·看图配对 —— 请求体"""
    keywords: List[str]               # 至少 2~6 个关键词（每个关键词生成一条音频 + 一张图片）
    hskLevel: int = Field(..., ge=1, le=6)
    textType: str = "一句话"
    lang: str = "zh-CN"
    difficulty: int = Field(2, ge=1, le=5)
    seed: Optional[int] = None        # 选填：用于固定打乱顺序的随机种子（可复现）

class MatchResp(BaseModel):
    """
    听力·看图配对 —— 响应体（与 MCResp 风格一致：字段扁平、直出 URL、选项用 dict 按 label 索引）
    - audios: 以 A/B/C... 为 key，value 含 子题ID/音频URL/（可选）文本
    - images: 以 A/B/C... 为 key，value 含 图片URL
    - answer_map: 标准答案映射（audio_label -> image_label）
      （若学生端不应暴露答案，可在路由层移除该字段）
    """
    exercise_id: str
    question_type: str = "听录音·看图配对"
    hsk_level: int
    difficulty: int
    audios: Dict[str, Dict[str, Any]]
    images: Dict[str, Dict[str, Any]]
    answer_map: Dict[str, str]

async def create_listen_image_match_exercise(cur, req: MatchReq) -> Dict[str, Any]:
    """
    创建一套“听录音·看图配对”题目：
    - 父题（LISTEN_IMAGE_MATCH）
    - N 个子题（每个关键词 → 一条听力 + 一张正确图片）
    - 返回与 MatchResp 完全对齐的结构（audios/images/answer_map）
    """
    # ---------- 0) 基础校验 ----------
    if not req.keywords or len(req.keywords) < 2 or len(req.keywords) > 6:
        raise ValueError("配对题关键词数量必须在 2~6 之间")
    # 复制一份，避免后续意外修改
    keywords = list(req.keywords)

    # ---------- 1) 为每个关键词生成听力文本 ----------
    hskExplain = HSK_LEVEL_DESCRIPTIONS.get(req.hskLevel, "无特定描述")
    textTypeExplain = TEXT_TYPE_INSTRUCTIONS.get(req.textType, "生成一个简单句子")

    listening_texts: List[str] = []
    for kw in keywords:
        prompt = f"""
作为中文教学内容设计师，请为“听录音·看图配对”题型生成一句听力文本。
- 目标关键词: `{kw}`
- HSK {req.hskLevel} ({hskExplain})
- 指定形式: {req.textType}（{textTypeExplain}）
- 要求: 文本自然、清晰，能被一张图片准确表达；避免多主体、多动作，避免抽象概念与时间线跳跃。
- 输出: 只输出最终文本，不要任何解释或标点以外的附加符号。
""".strip()
        text = generate_from_llm(prompt).strip()
        if not text:
            raise ValueError(f"AI 生成听力文本失败: {kw}")
        listening_texts.append(text)

    # ---------- 2) 生成并保存音频资产 ----------
    audio_asset_ids: List[str] = []
    for text in listening_texts:
        # 2.1 TTS（拿到临时 URL）
        audio_temp_url = generate_voice(text)  # 若 LLM_API_KEY 未设定，这里会抛错
        # 2.2 下载音频并入库存储
        resp = requests.get(audio_temp_url, timeout=30)
        resp.raise_for_status()
        audio_bytes = resp.content
        audio_mime = resp.headers.get("Content-Type", "audio/mpeg").split(";")[0]
        asset_id = save_audio_asset(cur, audio_bytes, audio_mime)
        audio_asset_ids.append(asset_id)

    # ---------- 3) 生成并保存图片资产 ----------
    image_asset_ids: List[str] = []
    for text in listening_texts:
        # 3.1 启动文生图任务
        img_prompt = f'根据以下描述生成一张清晰、写实、主体明确的图片，画面中不要出现任何文字或字母： "{text}"'
        init = generate_image(img_prompt, "文字, 字母, 模糊, 低质量, 变形")
        task_id = (init.get("output") or {}).get("task_id")
        if not task_id:
            raise ValueError("文生图任务未返回 task_id")

        # 3.2 轮询拿到图片 URL
        image_url = await _poll_image_task(task_id)
        if not image_url:
            raise ValueError("文生图任务失败或超时")

        # 3.3 下载图片并入库
        img_resp = requests.get(image_url, timeout=60)
        img_resp.raise_for_status()
        img_bytes = img_resp.content
        img_mime = img_resp.headers.get("Content-Type", "image/jpeg").split(";")[0]
        img_asset_id = save_image_asset(cur, img_bytes, img_mime)
        image_asset_ids.append(img_asset_id)

    # ---------- 4) 插入父题 ----------
    exercise_type_name = "LISTEN_IMAGE_MATCH"
    cur.execute("SELECT id FROM content_new.exercise_types WHERE name = %s;", (exercise_type_name,))
    row = cur.fetchone()
    if not row:
        raise ValueError(f"题型库中不存在题型: {exercise_type_name}")
    exercise_type_id = row[0]

    # 可把随机种子也落库，保证渲染顺序可复现（可选）
    parent_metadata = {
        "keywords": keywords,
        "seed": req.seed if req.seed is not None else None
    }
    parent_exercise_id = str(uuid.uuid4())
    cur.execute(
        """
        INSERT INTO content_new.exercises
            (id, exercise_type_id, prompt, metadata, difficulty_level)
        VALUES (%s, %s, %s, %s, %s);
        """,
        (parent_exercise_id, exercise_type_id,
         "请听每条音频，并与正确的图片进行配对。",
         json.dumps(parent_metadata), req.difficulty)
    )

    # ---------- 5) 插入子题并建立媒体关联 ----------
    sub_exercise_ids: List[str] = []
    for i, kw in enumerate(keywords):
        # 5.1 词库外键（可为空；你的业务若要求必须存在，这里抛错）
        cur.execute("SELECT id FROM content_new.words WHERE characters = %s;", (kw,))
        word_row = cur.fetchone()
        if not word_row:
            raise ValueError(f"词库中不存在词语: {kw}")
        word_id = word_row[0]

        # 5.2 子题记录
        sub_id = str(uuid.uuid4())
        sub_meta = {
            "listening_text": listening_texts[i],
            "correct_image_index": i   # 语义对应的图片索引（未打乱前的一一对应）
        }
        cur.execute(
            """
            INSERT INTO content_new.exercises
                (id, parent_exercise_id, word_id, exercise_type_id, prompt, metadata, difficulty_level, display_order)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
            """,
            (sub_id, parent_exercise_id, word_id, exercise_type_id,
             "请听录音，找到与之对应的图片。", json.dumps(sub_meta), req.difficulty, i)
        )

        # 5.3 媒体关联：音频 + 正确图片
        cur.execute(
            "INSERT INTO content_new.exercise_media_assets (exercise_id, media_asset_id, usage_role) VALUES (%s, %s, 'prompt_audio');",
            (sub_id, audio_asset_ids[i])
        )
        cur.execute(
            "INSERT INTO content_new.exercise_media_assets (exercise_id, media_asset_id, usage_role) VALUES (%s, %s, 'correct_image');",
            (sub_id, image_asset_ids[i])
        )

        sub_exercise_ids.append(sub_id)

    # ---------- 6) 将 asset_id 映射成公网 URL（直出给前端） ----------
    all_asset_ids = audio_asset_ids + image_asset_ids
    cur.execute(
        "SELECT id, file_url FROM content_new.media_assets WHERE id = ANY(%s::uuid[]);",
        (all_asset_ids,)
    )
    id2url = {str(r[0]): f"{MEDIA_PUBLIC_BASE}/{r[1]}" for r in cur.fetchall()}

    # ---------- 7) 生成标签并各自打乱；组装 audios/images/answer_map ----------
    n = len(sub_exercise_ids)
    labels = [chr(ord('A') + i) for i in range(n)]

    # 若提供 seed，则固定随机性，便于复现
    _rnd = random.Random(req.seed) if req.seed is not None else random

    audio_labels = labels[:]
    image_labels = labels[:]
    _rnd.shuffle(audio_labels)
    _rnd.shuffle(image_labels)

    audios: Dict[str, Dict[str, Any]] = {}
    images: Dict[str, Dict[str, Any]] = {}
    answer_map: Dict[str, str] = {}

    for i in range(n):
        a_lab = audio_labels[i]
        i_lab = image_labels[i]

        audios[a_lab] = {
            "sub_exercise_id": sub_exercise_ids[i],
            "audio_url": id2url.get(audio_asset_ids[i], ""),
            # 如不希望学生看到文本，可在路由层剔除这一行
            "listening_text": listening_texts[i]
        }
        images[i_lab] = {
            "image_url": id2url.get(image_asset_ids[i], "")
        }
        # 语义上一一对应：第 i 条音频 ↔ 第 i 张图片（但两侧标签各自打乱）
        answer_map[a_lab] = i_lab

    # ---------- 8) 返回与 MatchResp 完全对齐的结构 ----------
    return {
        "exercise_id": parent_exercise_id,
        "question_type": "听录音·看图配对",
        "hsk_level": req.hskLevel,
        "difficulty": req.difficulty,
        "audios": audios,
        "images": images,
        "answer_map": answer_map
    }


class ListenSentenceQAReq(BaseModel):
    keyword: str                         # 关联系统词（用于 words 外键）
    hskLevel: int = Field(..., ge=1, le=6)
    textType: str = "一句话"              # 复用 TEXT_TYPE_INSTRUCTIONS
    lang: str = "zh-CN"
    difficulty: int = Field(2, ge=1, le=5)
    optionCount: int = Field(3, ge=3, le=6)   # 选项数量，默认4
    seed: Optional[int] = None                # 可选：控制选项打乱的随机种子


class ListenSentenceQAResp(BaseModel):
    exercise_id: str
    question_type: str = "听录音·句子问答（单选）"
    hsk_level: int
    listening_text: str
    question: str
    question_pinyin:str
    audio_url: str
    options: Dict[str, Dict[str, Any]]        # {"A":{"text":"..."}, "B":{...}}
    correct_answer: str                        # "A" / "B" / ...

async def create_listen_sentence_qa_exercise(cur, req: ListenSentenceQAReq) -> Dict[str, Any]:
    """
    创建一道“听录音·句子问答（选择题版）”
    流程：生成听力句子 -> 生成单选题(题干+正确项+干扰项) -> 生成TTS并落库 -> 插入题目与媒体 -> 返回响应
    """
    # 1) 生成“听力文本”
    hskExplain = HSK_LEVEL_DESCRIPTIONS.get(req.hskLevel, "无特定描述")
    textTypeExplain = TEXT_TYPE_INSTRUCTIONS.get(req.textType, "生成一个简单句子")
    L_TXT_PROMPT = f"""
你是一名中文教学内容设计师，请为“听录音·句子问答（单选）”题型生成一句自然、清晰、易朗读的中文句子。
- 主题词: `{req.keyword}`
- HSK {req.hskLevel}（{hskExplain}）
- 形式: {req.textType}（{textTypeExplain}）
- 要求: 句子应包含可据此发问的明确事实（如人物/时间/地点/动作/数量等）。
- 输出: 只输出该句子本身。
""".strip()
    listening_text = generate_from_llm(L_TXT_PROMPT).strip()
    if not listening_text:
        raise ValueError("AI 生成听力文本失败")

    # 2) 基于听力文本生成【题干 + 正确项 + 干扰项们】
    #   让大模型一次输出结构化 JSON，便于解析
    n_opts = int(req.optionCount)
    QA_PROMPT = f"""
基于下列中文句子，设计一道“单选题”以考查对该句子的理解：
- 句子: "{listening_text}"
- 题干要求: 提出一个仅凭该句即可回答的单问题（谁/什么/何时/哪里/多少/为何/怎样等），不可开放式。
- 选项要求: 总共 {n_opts} 个；其中 1 个正确项 + {n_opts-1} 个干扰项；
  干扰项需“同一语义范畴、与句子贴近但不成立/不一致”，不能出现“以上都对/都不对/无法判断”这类选项。
- 输出 JSON（仅此结构，不要额外文字）：
{{
  "question": "……",
  "correct": "……",
  "distractors": ["……","……", "..."]   // 恰好 {n_opts-1} 个
}}
""".strip()
    qa_raw = generate_from_llm(QA_PROMPT).strip()
    try:
        qa = json.loads(qa_raw)
        question = str(qa["question"]).strip()
        correct_text = str(qa["correct"]).strip()
        distractors = [str(x).strip() for x in qa["distractors"]]
        if not question or not correct_text:
            raise ValueError("题干或正确项为空")
        if not isinstance(distractors, list) or len(distractors) != (n_opts - 1):
            raise ValueError(f"干扰项数量应为 {n_opts-1}")
        # 合法性小校验：不得包含完全相同文本
        all_texts = [correct_text] + distractors
        if len(set(all_texts)) != len(all_texts):
            raise ValueError("选项包含重复文本，请重试生成")
    except Exception as e:
        raise ValueError(f"AI 生成选择题 JSON 解析失败: {e}")
    
    question_pinyin = to_pinyin_sentence(question)
    correct_text_pinyin = to_pinyin_sentence(correct_text)
    distractors_pinyin = [to_pinyin_sentence(d) for d in distractors]

    # 3) 生成并保存音频（对“听力文本”进行TTS）
    audio_temp_url = generate_voice(listening_text)
    r = requests.get(audio_temp_url, timeout=30)
    r.raise_for_status()
    audio_bytes = r.content
    audio_mime = r.headers.get("Content-Type", "audio/mpeg").split(";")[0]
    audio_asset_id = save_audio_asset(cur, audio_bytes, audio_mime)

    # 4) 外键 & 题型检查
    # 4.1 word
    cur.execute("SELECT id FROM content_new.words WHERE characters = %s;", (req.keyword,))
    row = cur.fetchone()
    if not row:
        raise ValueError(f"词库中不存在词语: {req.keyword}")
    word_id = row[0]

    # 4.2 exercise_type
    ex_type_name = "LISTEN_SENTENCE_QA"
    cur.execute("SELECT id FROM content_new.exercise_types WHERE name=%s;", (ex_type_name,))
    row = cur.fetchone()
    if not row:
        raise ValueError(f"题型库中不存在题型: {ex_type_name}")
    exercise_type_id = row[0]

    # 5) 生成选项并打乱，确定正确标签
    options_texts: List[str] = [correct_text] + distractors
    rnd = random.Random(req.seed) if req.seed is not None else random
    rnd.shuffle(options_texts)

    labels = [chr(ord('A') + i) for i in range(n_opts)]
    label_to_text = {labels[i]: options_texts[i] for i in range(n_opts)}
    # 找出正确项的 label
    correct_label = None
    for lab, txt in label_to_text.items():
        if txt == correct_text:
            correct_label = lab
            break
    if not correct_label:
        raise RuntimeError("未能确定正确选项标签")

    # 6) 写 exercises（本题不需要子题）
    exercise_id = str(uuid.uuid4())
    all_texts = [correct_text] + distractors
    all_pinyins = [correct_text_pinyin] + distractors_pinyin
    text_to_pinyin_map = dict(zip(all_texts, all_pinyins))
    metadata = {
        "listening_text": listening_text,
        "question": question,
        "question_pinyin": question_pinyin,              # 新增
        "options": [
            {
                "label": lab, 
                "text": label_to_text[lab],
                "pinyin": text_to_pinyin_map.get(label_to_text[lab], "") # 新增
            } for lab in labels
        ],
        "correct_label": correct_label,
        "seed": req.seed
    }
    cur.execute(
        """
        INSERT INTO content_new.exercises
            (id, word_id, exercise_type_id, prompt, metadata, difficulty_level)
        VALUES (%s, %s, %s, %s, %s, %s);
        """,
        (exercise_id, word_id, exercise_type_id,
         "请先听录音，然后选择正确答案。", json.dumps(metadata), req.difficulty)
    )

    # 7) 关联音频
    cur.execute(
        "INSERT INTO content_new.exercise_media_assets (exercise_id, media_asset_id, usage_role) VALUES (%s, %s, 'prompt_audio');",
        (exercise_id, audio_asset_id)
    )

    # 8) 拼 URL & 组装响应（与 MCResp 风格一致）
    cur.execute("SELECT file_url FROM content_new.media_assets WHERE id=%s;", (audio_asset_id,))
    file_url = (cur.fetchone() or [""])[0]
    audio_url = f"{MEDIA_PUBLIC_BASE}/{file_url}"

    options_dict = {
        lab: {
            "text": label_to_text[lab],
            "pinyin": text_to_pinyin_map.get(label_to_text[lab], "") # 新增
        } for lab in labels
    }

    return {
        "exercise_id": exercise_id,
        "question_type": "听录音·句子问答（单选）",
        "hsk_level": req.hskLevel,
        "listening_text": listening_text,
        "question": question,
        "question_pinyin": question_pinyin,             # 新增
        "audio_url": audio_url,
        "options": options_dict,
        "correct_answer": correct_label
    }


class ListenSentenceTfReq(BaseModel):
    keyword: str                         # 关联系统词（用于 words 外键）
    hskLevel: int = Field(..., ge=1, le=6)
    isCorrect: bool = True               # True: 陳述与音频一致；False: 作为干扰项
    textType: str = "一句话"              # 复用 TEXT_TYPE_INSTRUCTIONS
    lang: str = "zh-CN"
    difficulty: int = Field(2, ge=1, le=5)
    seed: Optional[int] = None           # 可选：若后续需要复现随机性

class ListenSentenceTfResp(BaseModel):
    exercise_id: str
    question_type: str = "听录音·句子判断"
    hsk_level: int
    difficulty: int
    listening_text: str                  # 音频对应文本（如需隐藏，路由层去掉即可）
    statement: str
    statement_pinyin:str                       # 用于判断的文本陈述
    audio_url: str                       # 题干音频 URL
    correct_answer: bool                 # 标准答案（True/False）


async def create_listen_sentence_tf_exercise(cur, req: ListenSentenceTfReq) -> Dict[str, Any]:
    """
    创建一道“听录音·句子判断”题：
      1) 基于 keyword 生成听力文本
      2) TTS 生成音频并入库
      3) 生成判断用陈述（与音频一致/不一致）
      4) 写入 exercises / 关联媒体
      5) 返回可直接渲染的响应
    """
    # 1) 生成听力文本
    hskExplain = HSK_LEVEL_DESCRIPTIONS.get(req.hskLevel, "无特定描述")
    textTypeExplain = TEXT_TYPE_INSTRUCTIONS.get(req.textType, "生成一个简单、清晰的句子")
    L_PROMPT = f"""
你是一名严谨的中文教学内容设计师，请为“听录音·句子判断”题型生成一句自然、完整、易朗读的中文句子。
- 主题词: `{req.keyword}`
- HSK {req.hskLevel}（{hskExplain}）
- 形式: {req.textType}（{textTypeExplain}）
- 要求: 句子包含可核对的事实信息（人物/时间/地点/动作/数量等），避免含糊或多义。
- 输出: 只输出该句子本身。
""".strip()
    listening_text = generate_from_llm(L_PROMPT).strip()
    if not listening_text:
        raise ValueError("AI 生成听力文本失败")

    # 2) 生成并保存音频
    audio_temp_url = generate_voice(listening_text)  # 依赖 LLM_API_KEY
    resp = requests.get(audio_temp_url, timeout=30)
    resp.raise_for_status()
    audio_bytes = resp.content
    audio_mime = resp.headers.get("Content-Type", "audio/mpeg").split(";")[0]
    audio_asset_id = save_audio_asset(cur, audio_bytes, audio_mime)

    # 3) 生成判断陈述（根据 isCorrect 决定语义一致或不一致）
    if req.isCorrect:
        statement = listening_text  # 直接使用一致陈述
    else:
        W_PROMPT = f"""
基于下面这句中文，改写出一条与其“核心事实不一致”的陈述，用作判断题干扰项：
- 原句: "{listening_text}"
- 要求：仅改变一个关键要素（人物/时间/地点/动作或数量），保持句式难度与风格相当；不得出现否定词“不是/没有/不/并非”等显式提示；不得含额外解释。
- 输出：只输出干扰项句子。
""".strip()
        statement = generate_from_llm(W_PROMPT).strip()
        if not statement:
            raise ValueError("AI 生成干扰陈述失败")
    statement_pinyin=to_pinyin_sentence(statement)

    # 4) 外键与题型检查 + 落库
    # 4.1 words
    cur.execute("SELECT id FROM content_new.words WHERE characters = %s;", (req.keyword,))
    row = cur.fetchone()
    if not row:
        raise ValueError(f"词库中不存在词语: {req.keyword}")
    word_id = row[0]

    # 4.2 exercise_type（请先在 exercise_types 中配置 'LISTEN_SENTENCE_TF'）
    ex_type_name = "LISTEN_SENTENCE_TF"
    cur.execute("SELECT id FROM content_new.exercise_types WHERE name=%s;", (ex_type_name,))
    row = cur.fetchone()
    if not row:
        raise ValueError(f"题型库中不存在题型: {ex_type_name}")
    exercise_type_id = row[0]

    # 4.3 写 exercises（本题为单题，无子题）
    exercise_id = str(uuid.uuid4())
    metadata = {
        "listening_text": listening_text,
        "statement": statement,
        "statement_pinyin":statement_pinyin,
        "correct_answer": bool(req.isCorrect),
        "seed": req.seed
    }
    cur.execute(
        """
        INSERT INTO content_new.exercises
            (id, word_id, exercise_type_id, prompt, metadata, difficulty_level)
        VALUES (%s, %s, %s, %s, %s, %s);
        """,
        (exercise_id, word_id, exercise_type_id,
         "请先听录音，再判断下列陈述是否正确。", json.dumps(metadata), req.difficulty)
    )

    # 4.4 关联媒体（题干音频）
    cur.execute(
        "INSERT INTO content_new.exercise_media_assets (exercise_id, media_asset_id, usage_role) VALUES (%s, %s, 'prompt_audio');",
        (exercise_id, audio_asset_id)
    )

    # 5) 拼 URL 并返回
    cur.execute("SELECT file_url FROM content_new.media_assets WHERE id=%s;", (audio_asset_id,))
    file_url = (cur.fetchone() or [""])[0]
    audio_url = f"{MEDIA_PUBLIC_BASE}/{file_url}"

    return {
        "exercise_id": exercise_id,
        "question_type": "听录音·句子判断",
        "hsk_level": req.hskLevel,
        "difficulty": req.difficulty,
        "listening_text": listening_text,
        "statement": statement,
        "statement_pinyin":statement_pinyin,
        "audio_url": audio_url,
        "correct_answer": bool(req.isCorrect)
    }


class ReadImageTfReq(BaseModel):
    keyword: str
    hskLevel: int = Field(..., ge=1, le=2)
    isCorrect: bool = True           
    difficulty: int = Field(2, ge=1, le=5)

class ReadImageTfResp(BaseModel):
    exercise_id: str
    question_type: str = "阅读·图片·判断"
    hsk_level: int
    difficulty: int
    word: str
    pinyin: str
    image_url: str
    correct_answer: bool

async def create_read_image_tf_exercise(cur, req: ReadImageTfReq) -> Dict[str, Any]:
    """
    创建一道 阅读·图片·判断 题：
      - 输入 keyword
      - 生成对应图片（或干扰图）
      - 转换拼音
      - 落库
      - 返回响应
    """
    word = req.keyword.strip()
    if not word:
        raise ValueError("关键词不能为空")

    # 1) 生成拼音（调用你定义的工具函数）
    pinyin_str = to_pinyin_sentence(word)   # 假设返回 "zhōng wén"

    # 2) 根据 isCorrect 生成图片描述
    if req.isCorrect:
        img_prompt = f'请生成一张能够表现“{word}”含义的清晰图片，画面中不要出现任何文字或字母。'
    else:
        img_prompt = f'请生成一张与“{word}”无关的、完全不同主题的清晰图片，画面中不要出现任何文字或字母。'

    init = generate_image(img_prompt, "文字, 字母, 模糊, 低质量, 变形")
    task_id = (init.get("output") or {}).get("task_id")
    if not task_id:
        raise ValueError("文生图任务未返回 task_id")

    image_url = await _poll_image_task(task_id)
    if not image_url:
        raise ValueError("文生图任务失败或超时")

    # 下载图片
    r = requests.get(image_url, timeout=60)
    r.raise_for_status()
    img_bytes = r.content
    img_mime = r.headers.get("Content-Type", "image/jpeg").split(";")[0]
    image_asset_id = save_image_asset(cur, img_bytes, img_mime)

    # 3) 外键查找
    cur.execute("SELECT id FROM content_new.words WHERE characters = %s;", (word,))
    row = cur.fetchone()
    if not row:
        raise ValueError(f"词库中不存在词语: {word}")
    word_id = row[0]

    ex_type_name = "READ_IMAGE_TRUE_FALSE"
    cur.execute("SELECT id FROM content_new.exercise_types WHERE name=%s;", (ex_type_name,))
    row = cur.fetchone()
    if not row:
        raise ValueError(f"题型库中不存在题型: {ex_type_name}")
    exercise_type_id = row[0]

    # 4) 插入 exercises
    exercise_id = str(uuid.uuid4())
    metadata = {
        "word": word,
        "pinyin": pinyin_str,
        "correct_answer": bool(req.isCorrect)
    }
    cur.execute(
        """
        INSERT INTO content_new.exercises
            (id, word_id, exercise_type_id, prompt, metadata, difficulty_level)
        VALUES (%s, %s, %s, %s, %s, %s);
        """,
        (exercise_id, word_id, exercise_type_id,
         "请阅读该词语，再看图片，判断是否匹配。", json.dumps(metadata), req.difficulty)
    )

    # 5) 关联图片
    cur.execute(
        "INSERT INTO content_new.exercise_media_assets (exercise_id, media_asset_id, usage_role) VALUES (%s, %s, 'stem_image');",
        (exercise_id, image_asset_id)
    )

    # 6) 拼 URL 返回
    cur.execute("SELECT file_url FROM content_new.media_assets WHERE id=%s;", (image_asset_id,))
    file_url = (cur.fetchone() or [""])[0]
    public_url = f"{MEDIA_PUBLIC_BASE}/{file_url}"

    return {
        "exercise_id": exercise_id,
        "question_type": "阅读·图片·判断",
        "hsk_level": req.hskLevel,
        "difficulty": req.difficulty,
        "word": word,
        "pinyin": pinyin_str,
        "image_url": public_url,
        "correct_answer": bool(req.isCorrect)
    }



class ReadImageMatchReq(BaseModel):
    keywords: List[str]                 # 3–5 个词语
    hskLevel: int = Field(..., ge=1, le=6)
    difficulty: int = Field(2, ge=1, le=5)
    seed: Optional[int] = None          # 控制乱序的随机种子（可复现）

    @validator("keywords")
    def _check_len(cls, v):
        if not v or not (3 <= len(v) <= 5):
            raise ValueError("阅读·看图配对必须提供 3–5 个关键词")
        if any((not isinstance(w, str) or not w.strip()) for w in v):
            raise ValueError("关键词不能为空字符串")
        return [w.strip() for w in v]

class ReadImageMatchResp(BaseModel):
    exercise_id: str
    question_type: str = "阅读·看图配对"
    hsk_level: int
    difficulty: int
    texts: Dict[str, Dict[str, Any]]
    images: Dict[str, Dict[str, Any]]

    answer_map: Dict[str, str]



async def create_read_image_match_exercise(cur, req: ReadImageMatchReq) -> Dict[str, Any]:
    """
    创建一套“阅读·看图配对（3–5项）”题：
      - 父题：READ_IMAGE_MATCH
      - N 个子题：每个词 -> 拼音 + 正确图片（usage_role='correct_image'）
      - 返回与 ReadImageMatchResp 完全匹配（texts/images/answer_map）
    """
    words: List[str] = req.keywords
    n = len(words)

    # 1) 生成拼音（使用你提供的 to_pinyin_sentence）
    pinyins: List[str] = [to_pinyin_sentence(w) for w in words]

    # 2) 文生图：为每个词生成对应图片并入库
    image_asset_ids: List[str] = []
    for w in words:
        img_prompt = f'请生成一张能够清晰表现“{w}”含义的图片，画面中不要出现任何文字或字母。'
        init = generate_image(img_prompt, "文字, 字母, 模糊, 低质量, 变形")
        task_id = (init.get("output") or {}).get("task_id")
        if not task_id:
            raise ValueError("文生图任务未返回 task_id")

        image_url = await _poll_image_task(task_id)
        if not image_url:
            raise ValueError("文生图任务失败或超时")

        r = requests.get(image_url, timeout=60)
        r.raise_for_status()
        img_bytes = r.content
        img_mime = r.headers.get("Content-Type", "image/jpeg").split(";")[0]
        image_asset_id = save_image_asset(cur, img_bytes, img_mime)
        image_asset_ids.append(image_asset_id)

    # 3) 题型与词库外键
    ex_type_name = "READ_IMAGE_MATCH"
    cur.execute("SELECT id FROM content_new.exercise_types WHERE name=%s;", (ex_type_name,))
    row = cur.fetchone()
    if not row:
        raise ValueError(f"题型库中不存在题型: {ex_type_name}")
    exercise_type_id = row[0]

    word_ids: List[str] = []
    for w in words:
        cur.execute("SELECT id FROM content_new.words WHERE characters = %s;", (w,))
        row = cur.fetchone()
        if not row:
            raise ValueError(f"词库中不存在词语: {w}")
        word_ids.append(row[0])

    # 4) 插入父题
    parent_exercise_id = str(uuid.uuid4())
    parent_meta = {
        "keywords": words,
        "pinyin": pinyins,
        "seed": req.seed
    }
    cur.execute(
        """
        INSERT INTO content_new.exercises
            (id, exercise_type_id, prompt, metadata, difficulty_level)
        VALUES (%s, %s, %s, %s, %s);
        """,
        (parent_exercise_id, exercise_type_id,
         "请阅读词语，与正确的图片进行配对。", json.dumps(parent_meta), req.difficulty)
    )

    # 5) 插入 N 个子题并建立媒体关联（每个子题挂一张正确图片）
    sub_exercise_ids: List[str] = []
    for i in range(n):
        sub_id = str(uuid.uuid4())
        sub_meta = {
            "word": words[i],
            "pinyin": pinyins[i],
            "correct_image_index": i
        }
        cur.execute(
            """
            INSERT INTO content_new.exercises
                (id, parent_exercise_id, word_id, exercise_type_id, prompt, metadata, difficulty_level, display_order)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
            """,
            (sub_id, parent_exercise_id, word_ids[i], exercise_type_id,
             "请选择与该词语相符的图片。", json.dumps(sub_meta), req.difficulty, i)
        )
        cur.execute(
            "INSERT INTO content_new.exercise_media_assets (exercise_id, media_asset_id, usage_role) VALUES (%s, %s, 'correct_image');",
            (sub_id, image_asset_ids[i])
        )
        sub_exercise_ids.append(sub_id)

    # 6) 将 asset_id 映射为公网 URL
    cur.execute(
        "SELECT id, file_url FROM content_new.media_assets WHERE id = ANY(%s::uuid[]);",
        (image_asset_ids,)
    )
    id2url = {str(r[0]): f"{MEDIA_PUBLIC_BASE}/{r[1]}" for r in cur.fetchall()}

    # 7) 生成标签并各自乱序；texts / images / answer_map
    labels = [chr(ord('A') + i) for i in range(n)]  # A..E
    rnd = random.Random(req.seed) if req.seed is not None else random

    text_labels = labels[:]
    image_labels = labels[:]
    rnd.shuffle(text_labels)
    rnd.shuffle(image_labels)

    texts: Dict[str, Dict[str, Any]] = {}
    images: Dict[str, Dict[str, Any]] = {}
    answer_map: Dict[str, str] = {}

    for i in range(n):
        t_lab = text_labels[i]
        img_lab = image_labels[i]
        texts[t_lab] = {
            "sub_exercise_id": sub_exercise_ids[i],
            "word": words[i],
            "pinyin": pinyins[i]
        }
        images[img_lab] = {
            "image_url": id2url.get(image_asset_ids[i], "")
        }
        # 语义一一对应（第 i 个词 ↔ 第 i 张图），两侧乱序后用标签建立映射
        answer_map[t_lab] = img_lab

    # 8) 返回（与 ReadImageMatchResp 对齐）
    return {
        "exercise_id": parent_exercise_id,
        "question_type": "阅读·看图配对",
        "hsk_level": req.hskLevel,
        "difficulty": req.difficulty,
        "texts": texts,
        "images": images,
        "answer_map": answer_map
    }




class ReadingDialogMatchReq(BaseModel):
    keyword: str
    numPairs: int = Field(..., ge=3, le=6)      # 3~6 组
    hskLevel: int = Field(..., ge=1, le=6)
    difficulty: int = Field(2, ge=1, le=5)
    lang: str = "zh-CN"
    seed: Optional[int] = None                  # 固定乱序（可复现）

    @validator("keyword")
    def _kw_non_empty(cls, v):
        if not v or not v.strip():
            raise ValueError("keyword 不能为空")
        return v.strip()

class ReadingDialogMatchResp(BaseModel):
    question_type: str = "阅读·对话配对"
    hsk_level: int
    difficulty: int
    shuffled_questions: Dict[str, Dict[str, str]]   # {"A":{"text":"...","pinyin":"..."}}
    shuffled_answers: Dict[str, Dict[str, str]]     # {"B":{"text":"...","pinyin":"..."}}
    answers: Dict[str, str]                         # {"A":"C", ...}  左label -> 右label
    exercise_id: str



async def create_reading_dialog_matching(cur, req: ReadingDialogMatchReq):
    """
    生成【阅读·对话配对】并落库（新库版：content_new.*）。
    - LLM 产出 req.numPairs 组问答
    - 为每条问句/答句生成拼音（to_pinyin_sentence）
    - 父题：content_new.exercises（READ_DIALOGUE_MATCH）【现在强制关联 words】
    - 子题：每组一条，metadata 保存 utterance/utter_pinyin/reply/reply_pinyin
    - 返回：左右两列独立乱序 + label 映射
    """
    # 0) HSK 说明
    hskExplain = HSK_LEVEL_DESCRIPTIONS.get(req.hskLevel, "无特定描述")

    # 1) LLM 生成 pairs（与你现有一致）
    prompt_dialog = f"""
请围绕关键词“{req.keyword}”设计{req.numPairs}组一问一答的中文日常对话，适用于HSK{req.hskLevel}（{hskExplain}）。
要求：
1. 每组仅一问一答，语言自然简洁，角色不超过2人，单句不超过20个汉字；
2. 问答应语义匹配，可直接用于“对话配对”题；
3. 各组相互独立，不构成连续对话；
4. 仅返回 JSON：
{{
  "pairs": [
    {{ "question": "问句1", "answer": "回答1" }},
    {{ "question": "问句2", "answer": "回答2" }},
    ...
  ]
}}
5. 不要任何解释说明。
""".strip()

    raw = generate_from_llm(prompt_dialog).strip()
    try:
        pairs: List[Dict[str, str]] = json.loads(raw)["pairs"]
        if len(pairs) != req.numPairs:
            raise ValueError(f"LLM未返回指定数量：预期{req.numPairs}对，实际{len(pairs)}对。")
        for i, pair in enumerate(pairs, start=1):
            q, a = pair.get("question","").strip(), pair.get("answer","").strip()
            if not q or not a:
                raise ValueError(f"第{i}组缺少问句或答句")
            if len(q) > 40 or len(a) > 40:
                raise ValueError(f"第{i}组文本过长")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM返回解析失败或格式错误: {e}")

    # 2) 生成拼音
    questions = [p["question"].strip() for p in pairs]
    answers_texts = [p["answer"].strip() for p in pairs]
    q_pinyins = [to_pinyin_sentence(t) for t in questions]
    a_pinyins = [to_pinyin_sentence(t) for t in answers_texts]

    # 3) 乱序并建立映射（可复现）
    labels = ["A", "B", "C", "D", "E", "F"][: req.numPairs]
    rnd = random.Random(req.seed) if req.seed is not None else random
    q_idx = list(range(req.numPairs)); rnd.shuffle(q_idx)
    a_idx = list(range(req.numPairs)); rnd.shuffle(a_idx)

    shuffled_questions = {labels[i]: {"text": questions[q_idx[i]], "pinyin": q_pinyins[q_idx[i]]}
                          for i in range(req.numPairs)}
    shuffled_answers   = {labels[i]: {"text": answers_texts[a_idx[i]], "pinyin": a_pinyins[a_idx[i]]}
                          for i in range(req.numPairs)}

    inv_q_label = {v["text"]: k for k, v in shuffled_questions.items()}
    inv_a_label = {v["text"]: k for k, v in shuffled_answers.items()}
    answers_map = {inv_q_label[questions[i]]: inv_a_label[answers_texts[i]]
                   for i in range(req.numPairs)}

    # 4) 落库（新库）
    try:
        # 4.0 强制：父题必须关联 words 表
        cur.execute("SELECT id FROM content_new.words WHERE characters=%s;", (req.keyword,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=400, detail=f"词库中不存在词语：{req.keyword}（父题要求强制关联 words）")
        word_id = row[0]

        # 4.1 查题型
        cur.execute("SELECT id FROM content_new.exercise_types WHERE name=%s;", ("READ_DIALOGUE_MATCH",))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=400, detail="题型 READ_DIALOGUE_MATCH 未初始化，请先在 exercise_types 中插入。")
        exercise_type_id = row[0]

        # 4.2 父题（⚠ 加上 word_id）
        exercise_id = str(uuid.uuid4())
        parent_meta = {"keyword": req.keyword, "seed": req.seed}
        cur.execute("""
            INSERT INTO content_new.exercises
                (id, word_id, exercise_type_id, prompt, metadata, difficulty_level)
            VALUES (%s, %s, %s, %s, %s, %s);
        """, (
            exercise_id,
            word_id,  # ← 强制关联到词条
            exercise_type_id,
            "请将左侧问句与右侧恰当的回答进行配对。",
            json.dumps(parent_meta),
            req.difficulty
        ))

        # 4.3 子题（保持原样；不强制 word_id）
        for i in range(req.numPairs):
            sub_id = str(uuid.uuid4())
            sub_meta = {
                "utterance": questions[i],
                "utter_pinyin": q_pinyins[i],
                "reply": answers_texts[i],
                "reply_pinyin": a_pinyins[i],
                "pair_index": i
            }
            cur.execute("""
                INSERT INTO content_new.exercises
                    (id, parent_exercise_id, word_id, exercise_type_id, prompt, metadata, difficulty_level, display_order)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s);
            """, (
                sub_id,
                exercise_id,
                exercise_type_id,
                "匹配对话",
                json.dumps(sub_meta),
                req.difficulty,
                i
            ))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB error: {e}")

    # 5) 返回
    return ReadingDialogMatchResp(
        question_type="阅读·对话配对",
        hsk_level=req.hskLevel,
        difficulty=req.difficulty,
        shuffled_questions=shuffled_questions,
        shuffled_answers=shuffled_answers,
        answers=answers_map,
        exercise_id=exercise_id,
    )

class ReadingGapFillReq(BaseModel):
    keyword: str                         # 主题词/限定词
    hskLevel: int = Field(..., ge=1, le=6)
    difficulty: int = Field(2, ge=1, le=5)
    optionCount: int = 3  
    lang: str = "zh-CN"
    seed: Optional[int] = None


class ReadingGapFillResp(BaseModel):
    exercise_id: str
    question_type: str = "阅读·选词填空"
    hsk_level: int
    difficulty: int
    sentence_with_blank: str                 # 例：我 想 __ 一杯茶。
    options: Dict[str, Dict[str, str]]       # {"A":{"text":"点","pinyin":"diǎn"}, ...}
    correct_answer: str                      # 例："B"

async def create_reading_gap_fill_exercise(cur, req: ReadingGapFillReq) -> Dict[str, Any]:
    """
    生成【阅读·选词填空】并落库（content_new.*）
    - LLM 产出一句自然中文句子（包含 keyword 语境）
    - LLM 指定挖空词并给出同类干扰项
    - 计算所有选项拼音（to_pinyin_sentence）
    - 父题：content_new.exercises（READ_WORD_GAP_FILL）
    - 返回：句子+空格、选项(含拼音)、正确标签
    """
    kw = req.keyword.strip()
    if not kw:
        raise ValueError("keyword 不能为空")

    hskExplain = HSK_LEVEL_DESCRIPTIONS.get(req.hskLevel, "无特定描述")

    # 1) 生成基础句子
    sent_prompt = f"""
请用中文写一句自然、口语化、长度不超过20个汉字的句子，适用于HSK{req.hskLevel}（{hskExplain}），
与“{kw}”相关，但不要出现生僻词与人名地名。
仅输出这句话本身。
""".strip()
    sentence = generate_from_llm(sent_prompt).strip()
    if not sentence:
        raise ValueError("AI 生成句子失败")

    # 2) 让 LLM 选择挖空的词，并给出干扰项（同一词性/同语义域，避免“以上都对”等）
    gap_prompt = f"""
基于这句话："{sentence}"，设计一道“选词填空”。
要求：
1) 选择一句中的一个词作为空格（'gap_word'），该词语义明确；挖空后句子仍通顺；
2) 生成 {req.optionCount-1} 个干扰词（'distractors'），与 gap_word 词性/语义域一致，但放入句子后不成立或不自然；
3) 输出 JSON（仅以下字段）：
{{
  "gap_word": "……",
  "distractors": ["……","……", ...]   // 恰好 {req.optionCount-1} 个
}}
不要任何解释。
""".strip()
    raw = generate_from_llm(gap_prompt).strip()
    try:
        obj = json.loads(raw)
        gap_word = str(obj["gap_word"]).strip()
        distractors = [str(x).strip() for x in obj["distractors"]]
        if not gap_word:
            raise ValueError("gap_word 为空")
        if not isinstance(distractors, list) or len(distractors) != (req.optionCount - 1):
            raise ValueError("干扰项数量不匹配")
        # 去重 & 防止把相同词作为干扰项
        all_words = [gap_word] + distractors
        if len(set(all_words)) != len(all_words):
            raise ValueError("选项存在重复词语，请重试生成")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM 返回的挖空JSON解析失败: {e}")

    # 3) 构造“带空格”的句子（仅替换第一次出现的 gap_word）
    #    如果句子里不存在该词（偶发），回退为在句末合适位置插入空格提示
    if gap_word in sentence:
        sentence_with_blank = sentence.replace(gap_word, "__", 1)
    else:
        # 尽量不破坏句意的回退策略
        sentence_with_blank = sentence + " __"

    # 4) 计算选项拼音
    options_texts: List[str] = [gap_word] + distractors
    pinyins = [to_pinyin_sentence(w) for w in options_texts]

    # 5) 选项打乱并确定正确标签
    rnd = random.Random(req.seed) if req.seed is not None else random
    idxs = list(range(req.optionCount))
    rnd.shuffle(idxs)

    labels = [chr(ord('A') + i) for i in range(req.optionCount)]
    options_dict: Dict[str, Dict[str, str]] = {}
    correct_label: Optional[str] = None
    for pos, j in enumerate(idxs):
        lab = labels[pos]
        word_j = options_texts[j]
        py_j = pinyins[j]
        options_dict[lab] = {"text": word_j, "pinyin": py_j}
        if word_j == gap_word:
            correct_label = lab
    if not correct_label:
        raise RuntimeError("未能确定正确选项标签")

    # 6) 入库（新库）
    # 6.1 题型
    cur.execute("SELECT id FROM content_new.exercise_types WHERE name=%s;", ("READ_WORD_GAP_FILL",))
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=400, detail="题型 READ_WORD_GAP_FILL 未初始化，请先在 exercise_types 中插入。")
    exercise_type_id = row[0]

    # 6.2 （可选）把父题与词库关联：若你的业务需要强制关联到关键词
    cur.execute("SELECT id FROM content_new.words WHERE characters=%s;", (kw,))
    word_row = cur.fetchone()
    word_id = word_row[0] if word_row else None  # 若要强制，改成 if not row: raise ...

    exercise_id = str(uuid.uuid4())
    metadata = {
        "original_sentence": sentence,
        "gap_word": gap_word,
        "sentence_with_blank": sentence_with_blank,
        "options": [{"label": lab, "text": options_dict[lab]["text"], "pinyin": options_dict[lab]["pinyin"]}
                    for lab in labels],
        "correct_label": correct_label,
        "seed": req.seed
    }

    cur.execute(
        """
        INSERT INTO content_new.exercises
            (id, word_id, exercise_type_id, prompt, metadata, difficulty_level)
        VALUES (%s, %s, %s, %s, %s, %s);
        """,
        (
            exercise_id,
            word_id,  # 允许为空；若想强制，确保 words 里有 keyword，并在上面抛错
            exercise_type_id,
            "读句子，选出合适的词填空。",
            json.dumps(metadata),
            req.difficulty
        )
    )

    # 7) 返回（可直接渲染）
    return {
        "exercise_id": exercise_id,
        "question_type": "阅读·选词填空",
        "hsk_level": req.hskLevel,
        "difficulty": req.difficulty,
        "sentence_with_blank": sentence_with_blank,
        "options": options_dict,
        "correct_answer": correct_label
    }



class SentenceTransReq(BaseModel):
    keyword: str                          # 关联词（强制要求在 words 表存在）
    hskLevel: int = Field(..., ge=1, le=6)
    difficulty: int = Field(2, ge=1, le=5)
    seed: Optional[int] = None            # 预留，可做随机性控制（此题型用不到也可记录）

class SentenceTransResp(BaseModel):
    exercise_id: str
    question_type: str = "阅读·句子翻译"
    hsk_level: int
    difficulty: int
    sentence_cn: str
    sentence_en: str

async def create_sentence_translation_exercise(cur, req: SentenceTransReq) -> Dict[str, Any]:
    """
    生成【阅读·句子翻译】并落库：
    - 输入 keyword
    - LLM 产出与该词相关的一句中文 + 忠实的英文翻译（JSON）
    - 父题：content_new.exercises（READ_SENTENCE_TRANSLATION），强制关联 words
    - 返回：中文句子 + 英文翻译
    """
    kw = (req.keyword or "").strip()
    if not kw:
        raise ValueError("keyword 不能为空")

    hskExplain = HSK_LEVEL_DESCRIPTIONS.get(req.hskLevel, "无特定描述")

    # 1) 让 LLM 同时产出中文句子与英文翻译（严格 JSON）
    prompt = f"""
你是一名中文教学内容设计师。请基于词语“{kw}”为HSK{req.hskLevel}（{hskExplain}）生成一句自然、口语化的中文句子，
长度不超过20个汉字，避免专有名词与生僻字；并给出该句子的忠实英文翻译。
仅输出以下 JSON（不要任何解释）：
{{
  "cn": "……中文句子……",
  "en": "……英文翻译……"
}}
""".strip()

    raw = generate_from_llm(prompt).strip()
    try:
        obj = json.loads(raw)
        sentence_cn = str(obj["cn"]).strip()
        sentence_en = str(obj["en"]).strip()
        if not sentence_cn or not sentence_en:
            raise ValueError("句子或翻译为空")
        if len(sentence_cn) > 40:
            raise ValueError("中文句子过长")
    except Exception as e:
        # 由路由层捕获并转成 HTTPException 也可，这里直接抛出即可
        raise ValueError(f"LLM 返回解析失败或格式错误: {e}")

    # 2) 题型 / 词库 外键（父题强制关联 words）
    cur.execute("SELECT id FROM content_new.exercise_types WHERE name=%s;", ("READ_SENTENCE_TRANSLATION",))
    row = cur.fetchone()
    if not row:
        raise ValueError("题型库中不存在题型: READ_SENTENCE_TRANSLATION")
    exercise_type_id = row[0]

    cur.execute("SELECT id FROM content_new.words WHERE characters=%s;", (kw,))
    row = cur.fetchone()
    if not row:
        raise ValueError(f"词库中不存在词语：{kw}（本题型强制父题关联 words）")
    word_id = row[0]

    exercise_id = str(uuid.uuid4())
    metadata = {
        "keyword": kw,
        "sentence_cn": sentence_cn,
        "sentence_en": sentence_en,
        "seed": req.seed
    }
    cur.execute(
        """
        INSERT INTO content_new.exercises
            (id, word_id, exercise_type_id, prompt, metadata, difficulty_level)
        VALUES (%s, %s, %s, %s, %s, %s);
        """,
        (
            exercise_id,
            word_id,
            exercise_type_id,
            "请阅读中文句子，并给出对应英文翻译.",
            json.dumps(metadata),
            req.difficulty
        )
    )

    # 4) 返回（可直接作为 response_model=ReadSentenceTransResp）
    return {
        "exercise_id": exercise_id,
        "question_type": "阅读·句子翻译",
        "hsk_level": req.hskLevel,
        "difficulty": req.difficulty,
        "sentence_cn": sentence_cn,
        "sentence_en": sentence_en
    }



class ReadSentenceCompChoReq(BaseModel):
    keyword: str
    hskLevel: int = Field(..., ge=1, le=6)
    difficulty: int = Field(2, ge=1, le=5)
    seed: Optional[int] = None          

class ReadSentenceCompChoResp(BaseModel):
    exercise_id: str
    question_type: str = "阅读·句子理解"
    hsk_level: int
    difficulty: int
    passage: str
    question: str
    options: Dict[str, Dict[str, str]]  # {"A":{"text":"..."}, "B":{"text":"..."}, "C":{"text":"..."}}
    correct_answer: str                  # "A"/"B"/"C"


async def create_read_sentence_comprehension_choice_exercise(cur, req: ReadSentenceCompChoReq) -> Dict[str, Any]:
    """
    生成【阅读·句子理解】并落库：
      - 输入 keyword、HSK 等级与难度
      - LLM 依据提供的 prompt 生成：短文 + 题干 + 3 选项(A/B/C) + 正确答案
      - 题型：READ_SENTENCE_COMPREHENSION（需在 content_new.exercise_types 预置）
      - 返回：passage / question(含拼音) / options(含拼音) / correct_answer
    """
    kw = (req.keyword or "").strip()
    if not kw:
        raise ValueError("keyword 不能为空")
    hskExplain = HSK_LEVEL_DESCRIPTIONS.get(req.hskLevel, "无特定描述")

    # 1) 调用 LLM（严格 JSON）
    prompt = f"""
请根据以下要求生成一段连贯的文本，并根据文本内容设计语义理解选择题，并给出正确答案：
1. 请根据以下关键词：{kw} 生成连贯的文本。
2. 确保文本的语句通顺，内容积极向上，且符合HSK{req.hskLevel}级别（{hskExplain}）。
3. 文本长度为一两句话，文本包含20-50字。
4. 基于文本设计一个题目和三个选项（A/B/C），其中一个选项正确，其余为干扰项。
5. 返回严格JSON格式，不要多余文字或不可解析的字符：
{{
  "generated_text": "...",
  "question": "...",
  "options": ["...", "...", "..."],
  "answer": "A/B/C"
}}
""".strip()

    raw = generate_from_llm(prompt).strip()
    try:
        obj = json.loads(raw)
        passage: str = str(obj["generated_text"]).strip()
        question: str = str(obj["question"]).strip()
        options_list: List[str] = [str(x).strip() for x in obj["options"]]
        answer_label: str = str(obj["answer"]).strip().upper()
        if not passage or not question or len(options_list) != 3 or answer_label not in {"A","B","C"}:
            raise ValueError("字段缺失或不符合规范")
        if not (20 <= len(passage) <= 50):
            pass
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM 返回解析失败或格式错误: {e}")

    # [新增] 为题干和所有选项文本生成拼音
    question_pinyin = to_pinyin_sentence(question)
    options_pinyins = [to_pinyin_sentence(opt) for opt in options_list]
    # 创建一个从文本到拼音的映射，方便后续查找
    text_to_pinyin_map = dict(zip(options_list, options_pinyins))


    # 2) 选项打乱（保持可复现）
    orig_labels = ["A","B","C"]
    correct_text = options_list[orig_labels.index(answer_label)]

    rnd = random.Random(req.seed) if req.seed is not None else random
    idxs = [0,1,2]; rnd.shuffle(idxs)
    labels = ["A","B","C"]
    options: Dict[str, Dict[str, str]] = {}
    correct_label = None
    for pos, j in enumerate(idxs):
        lab = labels[pos]
        opt_text = options_list[j]
        # [修改] 在构建选项字典时，同时加入 text 和 pinyin
        options[lab] = {
            "text": opt_text,
            "pinyin": text_to_pinyin_map.get(opt_text, "")
        }
        if opt_text == correct_text:
            correct_label = lab
    if not correct_label:
        raise RuntimeError("未能确定正确选项标签")

    # 3) 题型 / 词库 外键（父题可选关联 words：如需强制，把不存在时改为 raise）
    cur.execute("SELECT id FROM content_new.exercise_types WHERE name=%s;", ("READ_SENTENCE_COMPREHENSION_CHOICE",))
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=400, detail="题型 READ_SENTENCE_COMPREHENSION_CHOICE 未初始化，请先在 exercise_types 中插入。")
    exercise_type_id = row[0]

    cur.execute("SELECT id FROM content_new.words WHERE characters=%s;", (kw,))
    word_row = cur.fetchone()
    word_id = word_row[0] if word_row else None

    # 4) 落库（单题，无子题/无媒体）
    exercise_id = str(uuid.uuid4())
    # [修改] 更新 metadata，为其增加 question_pinyin 和 options 里的 pinyin 字段
    metadata = {
        "keyword": kw,
        "passage": passage,
        "question": question,
        "question_pinyin": question_pinyin, # [新增]
        "options": [
            {
                "label": lab,
                "text": options[lab]["text"],
                "pinyin": options[lab]["pinyin"] # [新增]
            } for lab in labels
        ],
        "correct_label": correct_label,
        "seed": req.seed
    }
    cur.execute("""
        INSERT INTO content_new.exercises
            (id, word_id, exercise_type_id, prompt, metadata, difficulty_level)
        VALUES (%s, %s, %s, %s, %s, %s);
    """, (
        exercise_id,
        word_id,
        exercise_type_id,
        "请阅读短文，选择最符合语义的一项。",
        json.dumps(metadata),
        req.difficulty
    ))

    # 5) 返回（可直接作为 response_model=ReadSentenceComprResp）
    # [修改] 在返回的字典中也加入 question_pinyin
    return {
        "exercise_id": exercise_id,
        "question_type": "阅读·句子理解",
        "hsk_level": req.hskLevel,
        "difficulty": req.difficulty,
        "passage": passage,
        "question": question,
        "question_pinyin": question_pinyin, # [新增]
        "options": options,                 # 'options' 字典现在已经包含了拼音
        "correct_answer": correct_label
    }
class ReadSentenceTfReq(BaseModel):
    keyword: str
    hskLevel: int = Field(..., ge=1, le=6)
    difficulty: int = Field(2, ge=1, le=5)
    isCorrect: Optional[bool] = None
    seed: Optional[int] = None

class ReadSentenceTfResp(BaseModel):
    exercise_id: str
    question_type: str = "阅读·句子判断"
    hsk_level: int
    difficulty: int
    passage: str
    statement: str
    correct_answer: bool

async def create_read_sentence_tf_exercise(cur, req: ReadSentenceTfReq) -> Dict[str, Any]:
    """
    生成【阅读·句子判断】并落库（content_new.*）
    - 输入 keyword/HSK/difficulty
    - LLM 生成一段 20~50 字的短文
    - 生成一个判断陈述（与短文一致或相悖）
    - 父题：READ_SENTENCE_TF，无子题/无媒体
    """
    kw = (req.keyword or "").strip()
    if not kw:
        raise ValueError("keyword 不能为空")

    hskExplain = HSK_LEVEL_DESCRIPTIONS.get(req.hskLevel, "无特定描述")

    # 0) 决定正确性（True/False）
    rnd = random.Random(req.seed) if req.seed is not None else random
    is_correct = req.isCorrect if req.isCorrect is not None else rnd.choice([True, False])

    # 1) 生成短文（严格 JSON）
    passage_prompt = f"""
请根据以下要求生成一段连贯的中文文本：
- 关键词：{kw}
- 确保语句通顺、积极向上、符合HSK{req.hskLevel}（{hskExplain}）
- 长度：20~50字（一两句话）
只返回JSON：{{"text":"……"}}
""".strip()
    raw_passage = generate_from_llm(passage_prompt).strip()
    try:
        passage = str(json.loads(raw_passage)["text"]).strip()
        if not passage:
            raise ValueError("短文为空")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM 生成短文解析失败: {e}")

    # 2) 生成判断陈述（与短文一致 or 不一致）
    if is_correct:
        stmt_prompt = f"""
请基于下面这段话，写出一条与其“核心事实一致”的简短陈述，10~20字，避免重复原句与明显提示词（如“正确/错误”）。
原文：" {passage} "
只返回JSON：{{"statement":"……"}}
""".strip()
    else:
        stmt_prompt = f"""
请基于下面这段话，写出一条与其“核心事实不一致”的简短陈述，10~20字。
仅改变一个要素（人物/时间/地点/数量/动作），避免否定词提示（如“不是/没有/不/并非”）。
原文：" {passage} "
只返回JSON：{{"statement":"……"}}
""".strip()

    raw_stmt = generate_from_llm(stmt_prompt).strip()
    try:
        statement = str(json.loads(raw_stmt)["statement"]).strip()
        if not statement:
            raise ValueError("陈述为空")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM 生成陈述解析失败: {e}")

    # 3) 题型/词库外键（父题可选关联 words；若要强制，查不到时抛 400）
    cur.execute("SELECT id FROM content_new.exercise_types WHERE name=%s;", ("READ_SENTENCE_TF",))
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=400, detail="题型 READ_SENTENCE_TF 未初始化，请先在 exercise_types 中插入。")
    exercise_type_id = row[0]

    cur.execute("SELECT id FROM content_new.words WHERE characters=%s;", (kw,))
    row = cur.fetchone()
    word_id = row[0] if row else None
    # 如果要“强制父题关联词条”，改成：
    # if not row: raise HTTPException(status_code=400, detail=f"词库中不存在词语：{kw}")

    # 4) 入库（单题，无子题/无媒体）
    exercise_id = str(uuid.uuid4())
    metadata = {
        "keyword": kw,
        "passage": passage,
        "statement": statement,
        "correct_answer": bool(is_correct),
        "seed": req.seed
    }
    cur.execute("""
        INSERT INTO content_new.exercises
            (id, word_id, exercise_type_id, prompt, metadata, difficulty_level)
        VALUES (%s, %s, %s, %s, %s, %s);
    """, (
        exercise_id,
        word_id,
        exercise_type_id,
        "请阅读短文，判断陈述是否正确。",
        json.dumps(metadata),
        req.difficulty
    ))

    # 5) 返回（学生端可直接使用）
    return {
        "exercise_id": exercise_id,
        "question_type": "阅读·句子判断",
        "hsk_level": req.hskLevel,
        "difficulty": req.difficulty,
        "passage": passage,
        "statement": statement,
        "correct_answer": bool(is_correct)
    }


class ReadParagraphComprReq(BaseModel):
    topic: str
    hskLevel: int = Field(..., ge=1, le=6)
    difficulty: int = Field(2, ge=1, le=5)
    textLength: int = Field(100, ge=50, le=400)   # 文章目标字数（±10%）
    numQuestions: int = Field(3, ge=1, le=8)      # 生成题目数量
    seed: Optional[int] = None                    # 控制整体和选项打乱

class RPQuestionItem(BaseModel):
    sub_exercise_id: str
    stem: str
    options: Dict[str, Dict[str, str]]            # {"A":{"text":"..."}, ...}
    correct_answer: str                           # "A"~"D"

class ReadParagraphComprResp(BaseModel):
    exercise_id: str
    question_type: str = "阅读·段落理解"
    hsk_level: int
    difficulty: int
    passage: str
    highlighted_word: Optional[str] = None        # 文章中被 /.../ 包裹的词（若存在）
    questions: List[RPQuestionItem]

async def create_read_paragraph_comprehension_exercise(cur, req: ReadParagraphComprReq) -> Dict[str, Any]:
    """
    生成【阅读·段落理解（多题）】并落库（content_new.*）
    - 父题保存文章；每道单选题作为一个子题
    - 子题 metadata: {question, options:[{label,text}], correct_label}
    - 题型：READ_PARAGRAPH_COMPREHENSION（父/子同一题型）
    """
    topic = (req.topic or "").strip()
    if not topic:
        raise ValueError("topic 不能为空")
    hskExplain = HSK_LEVEL_DESCRIPTIONS.get(req.hskLevel, "无特定描述")
    rnd = random.Random(req.seed) if req.seed is not None else random

    # 1) 生成文章（严格 JSON，含 /词/ 标注）
    passage_prompt = f"""
请根据以下要求生成一段中文文章：
- **主题**：{topic}
- **HSK 等级**：HSK{req.hskLevel}（{hskExplain}）
- **字数**：约 {req.textLength} 字（可±10%）
- **风格**：句子通顺、逻辑自然、积极向上，可分为多个自然段；仅返回正文，不要任何解释或标题。
- **特殊要求**: 在文章中**随机**选择一个词汇，用斜杠 `/` 包裹起来，例如 `/稀有/`。
- **输出格式**：返回 JSON 格式，例如:
{{
  "generated_text": "文章正文"
}}
""".strip()
    raw_passage = generate_from_llm(passage_prompt).strip()
    try:
        passage_text = str(json.loads(raw_passage)["generated_text"]).strip()
        if not passage_text:
            raise ValueError("文章为空")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM 文章解析失败: {e}")

    # 抽取 /.../ 中的词（如果存在）
    m = re.search(r"/([^/\n]{1,10})/", passage_text)
    highlighted_word = m.group(1) if m else None

    # 2) 生成 N 道单选题（避免重复）
    questions_out: List[Dict[str, Any]] = []
    for i in range(req.numQuestions):
        existed = "\n".join([f'问题{idx+1}: {q["stem"]}' for idx, q in enumerate(questions_out)])
        existed_block = f"已有的问题如下，请避免生成相似或重复的问题：\n{existed}" if existed else ""
        q_prompt = f"""
请基于下面的中文文章，创建1道**单选题**（A~D四个选项，且仅一个正确）。
文章：
{passage_text}

{existed_block}

严格按 JSON 返回（不要多余文字）：
{{
  "question": "题干文本",
  "options": [
    {{"content": "选项A"}}, {{"content": "选项B"}}, {{"content": "选项C"}}, {{"content": "选项D"}}
  ],
  "correctIndex": 0
}}
""".strip()
        raw_q = generate_from_llm(q_prompt).strip()
        try:
            obj = json.loads(raw_q)
            stem = str(obj["question"]).strip()
            options_list = [str(o["content"]).strip() for o in obj["options"]]
            correct_idx = int(obj["correctIndex"])
            if not stem or len(options_list) != 4 or not (0 <= correct_idx <= 3):
                raise ValueError("题干/选项/答案不合法")
            # 简单去重：题干不能与已有完全相同
            if any(stem == q["stem"] for q in questions_out):
                raise ValueError("生成了重复题干")
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"LLM 题目解析失败（第{i+1}题）: {e}")

        correct_text = options_list[correct_idx]

        # 打乱选项并确定正确标签（可复现）
        idxs = list(range(4)); rnd.shuffle(idxs)
        labels = ["A", "B", "C", "D"]
        options_dict: Dict[str, Dict[str, str]] = {}
        correct_label = None
        for pos, j in enumerate(idxs):
            lab = labels[pos]
            txt = options_list[j]
            options_dict[lab] = {"text": txt}
            if txt == correct_text:
                correct_label = lab
        if not correct_label:
            raise RuntimeError("未能确定正确选项标签")

        questions_out.append({
            "stem": stem,
            "options": options_dict,
            "correct_label": correct_label
        })

    # 3) 题型外键

    cur.execute("SELECT id FROM content_new.exercise_types WHERE name=%s;",
                ("READ_PARAGRAPH_COMPREHENSION",))
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=400, detail="题型 READ_PARAGRAPH_COMPREHENSION 未初始化")
    exercise_type_id = row[0]

    # 3.1 强制：父题关联 words（用 topic 匹配 words.characters）
    cur.execute("SELECT id FROM content_new.words WHERE characters=%s;", (topic,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=400, detail=f"词库中不存在词语：{topic}")
    word_id = row[0]

    # 4) 写父题（⚠️ 加上 word_id）
    parent_id = str(uuid.uuid4())
    parent_meta = {
        "topic": topic,
        "passage": passage_text,
        "highlighted_word": highlighted_word,
        "num_questions": req.numQuestions,
        "seed": req.seed
    }
    cur.execute("""
        INSERT INTO content_new.exercises
            (id, word_id, exercise_type_id, prompt, metadata, difficulty_level)
        VALUES (%s, %s, %s, %s, %s, %s);
    """, (
        parent_id,
        word_id,                              # ← 这里写入 word_id
        exercise_type_id,
        "阅读文章，回答后面的选择题。",
        json.dumps(parent_meta),
        req.difficulty
    ))


    # 5) 写子题（每题一个子题，无媒体）
    sub_items: List[RPQuestionItem] = []
    for i, q in enumerate(questions_out):
        sub_id = str(uuid.uuid4())
        sub_meta = {
            "question": q["stem"],
            "options": [{"label": lab, "text": q["options"][lab]["text"]} for lab in ["A","B","C","D"]],
            "correct_label": q["correct_label"],
            "index": i
        }
        cur.execute("""
            INSERT INTO content_new.exercises
                (id, parent_exercise_id, exercise_type_id, prompt, metadata, difficulty_level, display_order)
            VALUES (%s, %s, %s, %s, %s, %s, %s);
        """, (
            sub_id, parent_id, exercise_type_id,
            "段落理解·单选题",
            json.dumps(sub_meta),
            req.difficulty,
            i
        ))
        sub_items.append(RPQuestionItem(
            sub_exercise_id=sub_id,
            stem=q["stem"],
            options=q["options"],
            correct_answer=q["correct_label"]
        ))

    # 6) 返回（父题 + 子题列表）
    return ReadParagraphComprResp(
        exercise_id=parent_id,
        hsk_level=req.hskLevel,
        difficulty=req.difficulty,
        passage=passage_text,
        highlighted_word=highlighted_word,
        questions=sub_items
    ).dict()


class WordOrderReq(BaseModel):
    keyword: str
    hskLevel: int = Field(..., ge=1, le=6)
    difficulty: int = Field(2, ge=1, le=5)
    lang: str = "zh-CN"
    seed: Optional[int] = None
    minPieces: int = Field(3, ge=2, le=10)
    maxPieces: int = Field(7, ge=3, le=12)

class WordOrderResp(BaseModel):
    exercise_id: str
    question_type: str = "阅读·连词成句"
    hsk_level: int
    difficulty: int
    # 乱序展示：每个词片含 id / text / pinyin
    pieces: Dict[str, Dict[str, str]]           # {"A":{"id":"...","text":"...","pinyin":"..."}}
    # 正确顺序：按“标签”的顺序 or 直接返回按原顺序的 piece_id 列表（更稳）
    answer_order: List[str]                      # 例如 ["C","A","B","D"]
    answer_ids: List[str]                        # 例如 ["id3","id1","id2","id4"]
    sentence: str                                # 可在学生端隐藏

async def create_word_order_exercise(cur, req: WordOrderReq) -> Dict[str, Any]:
    """
    阅读·连词成句（带拼音）：
      1) LLM 生成与 keyword 相关的一句中文
      2) segment_sentence() 切词
      3) 为每个词片计算拼音（逐词）
      4) 乱序并落库（content_new.exercises，题型 READ_WORD_ORDER）
      5) 返回：乱序词片(含拼音) + 正确顺序（标签 & id）
    依赖：generate_from_llm, segment_sentence, to_pinyin_sentence
    """
    kw = (req.keyword or "").strip()
    if not kw:
        raise ValueError("keyword 不能为空")
    hskExplain = HSK_LEVEL_DESCRIPTIONS.get(req.hskLevel, "无特定描述")

    # 1) 生成句子
    prompt = f"""
请用中文写一句与“{kw}”相关的自然口语化句子，适用于HSK{req.hskLevel}（{hskExplain}）。
- 长度建议 8~20 字，避免专名、生僻字和成语堆砌；
- 语序清晰，便于做“连词成句”；
- 仅输出这句话本身。
""".strip()
    sentence = generate_from_llm(prompt).strip()
    if not sentence:
        raise HTTPException(status_code=500, detail="AI 生成句子失败")

    # 2) 切词
    try:
        segs: List[str] = [s.strip() for s in segment_sentence(sentence) if s and s.strip()]
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"segment_sentence 执行失败: {e}")

    # 不在期望片段数范围则尝试改写并重切一次
    if len(segs) < req.minPieces or len(segs) > req.maxPieces:
        adjust_prompt = f"""
请改写这句话为更简洁、易于分词的一句中文（8~18字）：
“{sentence}”
只输出改写后的句子。
""".strip()
        sentence2 = generate_from_llm(adjust_prompt).strip() or sentence
        segs = [s.strip() for s in segment_sentence(sentence2) if s and s.strip()]
        sentence = sentence2
    if len(segs) < 2:
        raise HTTPException(status_code=500, detail="切分结果不足以组成连词成句题")

    # 3) 逐词拼音（对每个词片单独算）
    def word_pinyin(tok: str) -> str:
        # 你已有的 to_pinyin_sentence 通常支持整句，这里逐词调用即可
        return to_pinyin_sentence(tok)

    pieces_original = [
        {"id": str(uuid.uuid4()), "text": segs[i], "pinyin": word_pinyin(segs[i])}
        for i in range(len(segs))
    ]
    answer_ids = [p["id"] for p in pieces_original]  # 原顺序的 id 列表（最稳的答案表示）

    # 4) 乱序展示
    rnd = random.Random(req.seed) if req.seed is not None else random
    shuffled = pieces_original[:]
    rnd.shuffle(shuffled)

    labels = [chr(ord("A") + i) for i in range(len(shuffled))]  # A..?
    pieces_dict: Dict[str, Dict[str, str]] = {
        labels[i]: {"id": shuffled[i]["id"], "text": shuffled[i]["text"], "pinyin": shuffled[i]["pinyin"]}
        for i in range(len(shuffled))
    }

    # 5) 根据“原顺序 id”反查在乱序中的 label，得到 label 版答案（便于前端比对）
    id_to_label = {v["id"]: k for k, v in pieces_dict.items()}
    answer_order = [id_to_label[p["id"]] for p in pieces_original]

    # 6) 题型/词语外键并落库（强制父题关联词语）
    # 6.1 题型
    cur.execute("SELECT id FROM content_new.exercise_types WHERE name=%s;", ("READ_WORD_ORDER",))
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=400, detail="题型 READ_WORD_ORDER 未初始化，请先在 exercise_types 中插入。")
    exercise_type_id = row[0]

    # 6.2 词语（强制）
    cur.execute("SELECT id FROM content_new.words WHERE characters=%s;", (kw,))
    row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=400, detail=f"词库中不存在词语：{kw}")
    word_id = row[0]

    # 6.3 落库（单题，无子题/无媒体）
    exercise_id = str(uuid.uuid4())
    metadata = {
        "keyword": kw,
        "sentence": sentence,
        "pieces_original": pieces_original,                 # [{id,text,pinyin}...]
        "pieces_shuffled_label_map": pieces_dict,           # {A:{id,text,pinyin}...}
        "answer_order": answer_order,                       # 标签答案（便于前端）
        "answer_ids": answer_ids,                           # id 答案（最稳）
        "seed": req.seed
    }
    cur.execute("""
        INSERT INTO content_new.exercises
            (id, word_id, exercise_type_id, prompt, metadata, difficulty_level)
        VALUES (%s, %s, %s, %s, %s, %s);
    """, (
        exercise_id,
        word_id,
        exercise_type_id,
        "请将下列词片按正确顺序排列成句。",
        json.dumps(metadata),
        req.difficulty
    ))

    # 7) 返回（学生端可直接用；如需隐藏原句，可在路由层剔除）
    return {
        "exercise_id": exercise_id,
        "question_type": "阅读·连词成句",
        "hsk_level": req.hskLevel,
        "difficulty": req.difficulty,
        "pieces": pieces_dict,            # 含 pinyin
        "answer_order": answer_order,     # 标签序
        "answer_ids": answer_ids,         # id 序
        "sentence": sentence
    }









