import os
import io
import json
import mimetypes
import hashlib
import asyncio
import subprocess
from datetime import datetime
from typing import Optional, Tuple,Dict,Any,List

import uuid
import psycopg2
import requests
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from PIL import Image
import random

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


class GenerateReq(BaseModel):
    keyword: str
    hskLevel: int = Field(..., ge=1, le=6)
    isCorrect: bool = True
    textType: str = "一句话"
    lang: str = "zh-CN"
    difficulty: int = Field(2, ge=1, le=5)
    seed: Optional[int] = None


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