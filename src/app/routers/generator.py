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

def save_image_bytes(data: bytes, mime_type: str) -> Tuple[str, str, int, int, int, str]:
    sha = _sha256(data)
    y, m, d = _date_parts()
    prefix = sha[:2]
    ext = _guess_ext(mime_type, ".jpg")
    rel_path = f"images/{y}/{m}/{d}/{prefix}/{sha}{ext}"
    abs_path = os.path.join(MEDIA_ROOT, rel_path)
    _ensure_dir(os.path.dirname(abs_path))
    img = Image.open(io.BytesIO(data))
    w, h = img.size
    with open(abs_path, "wb") as f:
        f.write(data)
    url = f"{MEDIA_PUBLIC_BASE}/{rel_path}"
    return url, rel_path, len(data), w, h, sha

def save_audio_bytes(data: bytes, mime_type: str) -> Tuple[str, str, int, Optional[int], str]:
    sha = _sha256(data)
    y, m, d = _date_parts()
    prefix = sha[:2]
    ext = _guess_ext(mime_type, ".mp3")
    rel_path = f"audios/{y}/{m}/{d}/{prefix}/{sha}{ext}"
    abs_path = os.path.join(MEDIA_ROOT, rel_path)
    _ensure_dir(os.path.dirname(abs_path))
    with open(abs_path, "wb") as f:
        f.write(data)
    duration_ms = _ffprobe_duration_ms(abs_path)
    url = f"{MEDIA_PUBLIC_BASE}/{rel_path}"
    return url, rel_path, len(data), duration_ms, sha

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

class GenerateResp(BaseModel):
    question_type: str
    hsk_level: int
    listening_text: str
    audio_url: str
    image_url: str
    correct_answer: str
    exercise_id: str


router = APIRouter()
# 听录音 看图判断
@router.post("/api/generate/listen-image-tf", response_model=GenerateResp)
async def generate_listen_image_tf(body: GenerateReq):
    hskExplain = HSK_LEVEL_DESCRIPTIONS.get(body.hskLevel, "无特定描述")
    textTypeExplain = TEXT_TYPE_INSTRUCTIONS.get(body.textType, "生成一个简单的句子")

    RIGHT_PROMPT_TEMPLATE = f"""
作为一名顶尖的中文教学内容（CSL）设计师，请为“看图判断”题型创作一段高质量的中文文本。
- 核心词汇: 文本必须围绕 `{body.keyword}` 展开。
- 场景要求: 文本必须描述一个清晰、具体、可以用图像轻松表现的场景或动作。
- 目标等级: HSK {body.hskLevel} ({hskExplain})
- 指定形式: {textTypeExplain}
- 输出格式: 请直接输出最终生成的文本，不要包含任何标签。
""".strip()

    listening_text = generate_from_llm(RIGHT_PROMPT_TEMPLATE).strip()
    if not listening_text:
        raise HTTPException(status_code=500, detail="AI生成听力文本失败")

    # 2) 生成 TTS 音频 URL，并做 OSS 转链（可选），然后下载字节保存本地
    audio_temp_url = generate_voice(listening_text)
    if not audio_temp_url:
        raise HTTPException(status_code=500, detail="语音生成失败，未能获取URL")

    oss_audio_url = url_without_course(audio_temp_url)
    if not oss_audio_url:
        raise HTTPException(status_code=500, detail="语音OSS链接转化失败")

    audio_resp = requests.get(audio_temp_url, timeout=30)
    if not audio_resp.ok:
        raise HTTPException(status_code=500, detail="下载音频失败")
    audio_bytes = audio_resp.content
    audio_mime = audio_resp.headers.get("Content-Type", "audio/mpeg").split(";")[0]
    audio_public_url, audio_rel, audio_size, audio_dur_ms, audio_sha = save_audio_bytes(audio_bytes, audio_mime)

    # 3) 生成“与陈述一致/不一致”的图像描述 → 文生图 task → 轮询 → 拿 URL → 转链 → 下载保存
    if body.isCorrect:
        image_description_text = listening_text
        final_answer = "正确"
    else:
        WRONG_PROMPT_TEMPLATE = f"""
作为一名严谨的中文试题设计师，你的任务是创作一个与原始句子【相似度极低】的全新句子，用作“看图判断”题的干扰项。
- 原始句子 (HSK {body.hskLevel} 水平): "{listening_text}"
- 核心生成要求:
  1. 主题和场景必须完全不同；
  2. 严禁使用关键词；
  3. 难度和结构对等；
  4. 必须可被清晰地转换成一张图片。
- 输出要求: 只输出新句子，不要解释。
""".strip()
        wrong_text = generate_from_llm(WRONG_PROMPT_TEMPLATE).strip()
        if not wrong_text:
            raise HTTPException(status_code=500, detail="AI生成干扰项文本失败")
        image_description_text = wrong_text
        final_answer = "错误"

    image_prompt = f'请根据以下描述生成一张清晰、写实的图片，画面中不要出现任何文字： "{image_description_text}"'
    init = generate_image(image_prompt, "文字, 丑陋, 模糊")
    task_id = init.get("output", {}).get("task_id")
    if not task_id:
        raise HTTPException(status_code=500, detail="文生图任务未返回 task_id")

    image_url = None
    for _ in range(20):
        status = get_text_to_image_task_status(task_id)
        task_status = status.get("output", {}).get("task_status")
        if task_status == "SUCCEEDED":
            image_url = status.get("output", {}).get("results", [{}])[0].get("url")
            break
        elif task_status == "FAILED":
            raise HTTPException(status_code=500, detail="文生图任务失败")
        await asyncio.sleep(1.5) # 使用 await
    if not image_url:
        raise HTTPException(status_code=500, detail="未获取到图片URL")

    oss_image_url = url_without_course(image_url)
    if not oss_image_url:
        raise HTTPException(status_code=500, detail="图片OSS链接转化失败")

    img_resp = requests.get(oss_image_url, timeout=60)
    if not img_resp.ok:
        raise HTTPException(status_code=500, detail="下载图片失败")
    img_bytes = img_resp.content
    img_mime = img_resp.headers.get("Content-Type", "image/jpeg").split(";")[0]
    image_public_url, image_rel, image_size, w, h, img_sha = save_image_bytes(img_bytes, img_mime)

    # 4) 事务写库
    exercise_id = None
    try:
        with _db() as conn:
            with conn.cursor() as cur:
                # asset: audio
                cur.execute("""
                    INSERT INTO content.asset
                      (media_kind, url, file_path, mime_type, size_bytes, duration_ms, checksum_sha256, meta)
                    VALUES
                      ('audio', %s, %s, %s, %s, %s, %s,
                        jsonb_build_object('source_url', %s))
                    RETURNING id
                """, (audio_public_url, audio_rel, audio_mime, audio_size, audio_dur_ms, audio_sha, oss_audio_url))
                audio_asset_id = cur.fetchone()[0]

                # asset: image
                cur.execute("""
                    INSERT INTO content.asset
                      (media_kind, url, file_path, mime_type, size_bytes, width, height, checksum_sha256, meta)
                    VALUES
                      ('image', %s, %s, %s, %s, %s, %s, %s,
                        jsonb_build_object('prompt', %s, 'source_url', %s))
                    RETURNING id
                """, (image_public_url, image_rel, img_mime, image_size, w, h, img_sha, image_prompt, oss_image_url))
                image_asset_id = cur.fetchone()[0]

                # exercise

                cur.execute("""
                    INSERT INTO content.exercise
                    (skill, format, title, stem_text, lang, hsk_level, difficulty, points)
                 VALUES
                    ('listening', 'picture_tf',
                    '听录音，看图判断',
                    '请听录音，再看图片，判断陈述是否正确。',
                    %s, %s, %s, 1.0)
                    RETURNING id
                """, (body.lang, body.hskLevel, body.difficulty))  
                exercise_id = cur.fetchone()[0]


                # detail
                cur.execute("""
                    INSERT INTO content.exercise_tf_detail
                      (exercise_id, correct_is_true, explanation, transcript_text, core_keyword, meta)
                    VALUES
                      (%s, %s, %s, %s, %s,
                        jsonb_build_object('statement', %s, 'mode', %s))
                """, (
                    exercise_id,
                    True if body.isCorrect else False,
                    "图文一致为“正确”，不一致为“错误”。",
                    None,
                    body.keyword,
                    listening_text,
                    "consistent" if body.isCorrect else "inconsistent"
                ))

                # 关联音频
                cur.execute("""
                    INSERT INTO content.exercise_asset
                      (exercise_id, asset_id, role, position)
                    VALUES (%s, %s, 'audio', 1)
                """, (exercise_id, audio_asset_id))

                # 关联题图
                cur.execute("""
                    INSERT INTO content.exercise_asset
                      (exercise_id, asset_id, role, position)
                    VALUES (%s, %s, 'stem_image', 1)
                """, (exercise_id, image_asset_id))

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB error: {e}")

    # 5) 返回
    return GenerateResp(
        question_type="听录音，看图判断",
        hsk_level=body.hskLevel,
        listening_text=listening_text,
        audio_url=audio_public_url,
        image_url=image_public_url,
        correct_answer="正确" if body.isCorrect else "错误",
        exercise_id=str(exercise_id),
    )



class MCReq(BaseModel):
    correctKeyword: str
    hskLevel: int = Field(..., ge=1, le=6)
    textType: str = "一句话"
    lang: str = "zh-CN"
    difficulty: int = Field(2, ge=1, le=5)

class MCResp(BaseModel):
    question_type: str
    hsk_level: int
    listening_text: str
    audio_url: str
    options: Dict[str, Dict[str, Any]]  # { "A": {"keyword":..., "image_url":...}, ... }
    correct_answer: str                 # "A" / "B" / "C"
    exercise_id: str

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

#听录音 看图选择
@router.post("/api/generate/listen-image-mc", response_model=MCResp)
async def generate_listen_image_mc(body: MCReq):
    """生成【听录音·看图选择（单选）】并落库"""
    hskExplain = HSK_LEVEL_DESCRIPTIONS.get(body.hskLevel, "无特定描述")
    textTypeExplain = TEXT_TYPE_INSTRUCTIONS.get(body.textType, "生成一个单一、完整的句子。")

    # 1) 生成听力文本
    RIGHT_PROMPT_TEMPLATE = f"""
作为一名顶尖的中文教学内容（CSL）设计师，你的核心任务是为“听录音，看图选择”题型创作一段高质量的中文听力文本。
**1. 核心词汇**
- 文本内容必须围绕以下关键词展开：`{body.correctKeyword}`。
**2. 场景要求**
- 文本必须描述一个清晰、具体、单一、可以用图像轻松表现的场景或动作。
**3. 语言水平要求 (HSK)**
- 目标等级: HSK {body.hskLevel}
- 等级说明: {hskExplain}
**4. 文本形式要求**
- 指定形式: {body.textType}
- 形式说明: {textTypeExplain}
**5. 输出格式**
- 只输出最终文本，不要任何解释/标题/标签。
""".strip()

    listening_text = generate_from_llm(RIGHT_PROMPT_TEMPLATE).strip()
    if not listening_text:
        raise HTTPException(status_code=500, detail="AI生成听力文本失败")

    # 2) 生成 TTS 音频并保存到本地 (asset)
    audio_temp_url = generate_voice(listening_text)
    if not audio_temp_url:
        raise HTTPException(status_code=500, detail="TTS 未返回 URL")

    audio_resp = requests.get(audio_temp_url, timeout=30)
    if not audio_resp.ok:
        raise HTTPException(status_code=500, detail="下载音频失败")
    audio_bytes = audio_resp.content
    audio_mime = audio_resp.headers.get("Content-Type", "audio/mpeg").split(";")[0]
    audio_public_url, audio_rel, audio_size, audio_dur_ms, audio_sha = save_audio_bytes(audio_bytes, audio_mime)

    # 3) 让 LLM 生成两个干扰关键词（与正确关键词并列出题）
    distractor_prompt = f'请为“{body.correctKeyword}”设计两个中文词汇，作为“听录音，看图选择”题的干扰项。输出格式为 JSON 数组，例如：["干扰词1","干扰词2"]，不要添加其他内容。'
    ds_raw = generate_from_llm(distractor_prompt).strip()
    try:
        distractors: List[str] = json.loads(ds_raw)
        distractors = [str(x).strip() for x in distractors if str(x).strip()]
    except Exception:
        raise HTTPException(status_code=500, detail="干扰词返回格式非法（非JSON数组）")
    if len(distractors) < 2:
        raise HTTPException(status_code=500, detail="干扰词不足2个")

    # 4) 生成三张图片（正确项=根据听力文本，干扰项=名词直拍）
    #    先随机洗牌 A/B/C
    options_raw = [body.correctKeyword] + distractors[:2]
    import random
    random.shuffle(options_raw)
    label_list = ["A", "B", "C"]
    answer_index = options_raw.index(body.correctKeyword)
    answer_letter = label_list[answer_index]

    option_images: Dict[str, Tuple[str, str, int, int, int, str]] = {}  # label -> save_image_bytes返回元组
    option_keywords: Dict[str, str] = {}  # label -> keyword
    option_source_urls: Dict[str, str] = {}

    for i, kw in enumerate(options_raw):
        label = label_list[i]
        if kw == body.correctKeyword:
            image_prompt = f'请根据以下描述生成一张清晰、写实的图片，画面中不要出现任何文字： "{listening_text}"'
        else:
            image_prompt = f'高质量照片，主体是一个“{kw}”；背景简单、构图清晰；不要文字。'

        init = generate_image(image_prompt, "文字, 丑陋, 模糊")
        task_id = (init.get("output") or {}).get("task_id")
        if not task_id:
            raise HTTPException(status_code=500, detail="文生图任务未返回 task_id")

        img_url = await _poll_image_task(task_id)
        if not img_url:
            raise HTTPException(status_code=500, detail="文生图任务失败或超时")

        # 可选：转内链/CDN
        oss_image_url = url_without_course(img_url) or img_url

        # 下载并保存到本地
        img_resp = requests.get(oss_image_url, timeout=60)
        if not img_resp.ok:
            raise HTTPException(status_code=500, detail="下载图片失败")
        img_bytes = img_resp.content
        img_mime = img_resp.headers.get("Content-Type", "image/jpeg").split(";")[0]
        saved = save_image_bytes(img_bytes, img_mime)  # -> (public_url, rel_path, size, w, h, sha)
        option_images[label] = saved
        option_keywords[label] = kw
        option_source_urls[label] = oss_image_url

    # 5) 事务落库
    try:
        with _db() as conn:
            with conn.cursor() as cur:
                # 5.1 asset: 音频
                cur.execute("""
                    INSERT INTO content.asset
                      (media_kind, url, file_path, mime_type, size_bytes, duration_ms, checksum_sha256, meta)
                    VALUES
                      ('audio', %s, %s, %s, %s, %s, %s,
                       jsonb_build_object('source_url', %s))
                    RETURNING id
                """, (audio_public_url, audio_rel, audio_mime, audio_size, audio_dur_ms, audio_sha, audio_temp_url))
                audio_asset_id = cur.fetchone()[0]

                # 5.2 exercise 主表
                cur.execute("""
                    INSERT INTO content.exercise
                      (skill, format, title, stem_text, lang, hsk_level, difficulty, points)
                    VALUES
                      ('listening','picture_choice',
                       '听录音·看图选择',
                       '请听录音，再从三张图片中选择与录音描述一致的一项。',
                       %s, %s, %s, 1.0)
                    RETURNING id
                """, (body.lang, body.hskLevel, body.difficulty))
                exercise_id = cur.fetchone()[0]

                # 5.3 判断题细节（可选：兼容你的判分器，写入“正确为与文本一致”）
                #     这里把听力文本也放入 transcript_text，便于前端直接读取
                cur.execute("""
                    INSERT INTO content.exercise_tf_detail
                      (exercise_id, correct_is_true, explanation, transcript_text, core_keyword, meta)
                    VALUES
                      (%s, TRUE,
                       '与录音内容一致的图片为正确答案。',
                       %s,
                       %s,
                       jsonb_build_object('statement', %s, 'mode', 'mc_image'))
                """, (exercise_id, listening_text, body.correctKeyword, listening_text))

                # 5.4 关联音频
                cur.execute("""
                    INSERT INTO content.exercise_asset
                      (exercise_id, asset_id, role, position)
                    VALUES (%s, %s, 'audio', 1)
                """, (exercise_id, audio_asset_id))

                # 5.5 生成三张图片的 asset + option + exercise_asset + answer_key
                option_ids: Dict[str, str] = {}
                for i, label in enumerate(label_list):
                    pub_url, rel_path, size_b, w, h, sha = option_images[label]
                    kw = option_keywords[label]
                    src = option_source_urls[label]

                    # asset: image
                    cur.execute("""
                        INSERT INTO content.asset
                          (media_kind, url, file_path, mime_type, size_bytes, width, height, checksum_sha256, meta)
                        VALUES
                          ('image', %s, %s, %s, %s, %s, %s, %s,
                           jsonb_build_object('prompt', %s, 'source_url', %s))
                        RETURNING id
                    """, (pub_url, rel_path, "image/jpeg", size_b, w, h, sha,
                          ("根据听力文本生成" if kw == body.correctKeyword else f"实体物体：{kw}"),
                          src))
                    image_asset_id = cur.fetchone()[0]

                    # option
                    cur.execute("""
                        INSERT INTO content.option
                          (exercise_id, label, text, order_no, extra)
                        VALUES
                          (%s, %s, %s, %s, jsonb_build_object('keyword', %s))
                        RETURNING id
                    """, (exercise_id, label, kw, i + 1, kw))
                    option_id = cur.fetchone()[0]
                    option_ids[label] = option_id

                    # 题目与该选项图片关联（role=option_image + option_id）
                    cur.execute("""
                        INSERT INTO content.exercise_asset
                          (exercise_id, asset_id, role, position, option_id)
                        VALUES
                          (%s, %s, 'option_image', %s, %s)
                    """, (exercise_id, image_asset_id, i + 1, option_id))

                # 5.6 答案（把正确项写入 answer_key）
                cur.execute("""
                    INSERT INTO content.answer_key
                      (exercise_id, option_id, is_correct, score)
                    VALUES
                      (%s, %s, TRUE, 1.0)
                """, (exercise_id, option_ids[answer_letter]))

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB error: {e}")

    # 6) 返回给前端
    opt_payload = {
        label: {"keyword": option_keywords[label], "image_url": option_images[label][0]}
        for label in label_list
    }
    return MCResp(
        question_type="听录音·看图选择（单选）",
        hsk_level=body.hskLevel,
        listening_text=listening_text,
        audio_url=audio_public_url,
        options=opt_payload,
        correct_answer=answer_letter,
        exercise_id=str(exercise_id),
    )


class MatchReq(BaseModel):
    keywordsList: List[str]
    hskLevel: int = Field(..., ge=1, le=6)
    textTypesList: List[str]
    lang: str = "zh-CN"
    difficulty: int = Field(2, ge=1, le=5)

class MatchResp(BaseModel):
    question_type: str
    hsk_level: int
    shuffled_images: Dict[str, str]  # {"A":url, "B":url, ...}
    items: List[Dict[str, Any]]      # [{item_number, listening_text, image_url}]
    combined_audio: Dict[str, str]   # {text, url}
    answers: Dict[str, str]          # {"1":"C", "2":"A", ...}
    exercise_id: str

#听录音 看图配对
@router.post("/api/generate/listen-image-matching", response_model=MatchResp)
async def generate_listen_image_matching(body: MatchReq):
    if len(body.keywordsList) != len(body.textTypesList) or not (2 <= len(body.keywordsList) <= 6):
        raise HTTPException(status_code=400, detail="keywordsList 与 textTypesList 长度需一致，且在 [2,6] 之间")

    hskExplain = HSK_LEVEL_DESCRIPTIONS.get(body.hskLevel, "无特定描述")

    generated_items: List[Dict[str, Any]] = []
    for idx, keyword in enumerate(body.keywordsList):
        textType = body.textTypesList[idx]
        textTypeExplain = TEXT_TYPE_INSTRUCTIONS.get(textType, "生成一个简单的句子")

        prompt = f"""
作为一名顶尖的中文教学内容（CSL）设计师，你的核心任务是为“看图配对”题型创作一段高质量中文文本。
**1. 核心词汇**：必须围绕 `{keyword}` 展开。
**2. 场景要求**：清晰、具体、单一、且便于图像呈现。
**3. 语言水平**：HSK {body.hskLevel}（{hskExplain}）。
**4. 文本形式**：{textType}（{textTypeExplain}）。
**5. 输出**：只输出最终文本，不要任何解释/标签。
        """.strip()

        raw_text = generate_from_llm(prompt).strip()
        if not raw_text:
            raise HTTPException(status_code=500, detail=f"为关键词“{keyword}”生成文本失败")

        listening_text = raw_text  # 如需改写，可在此加 rewrite 流程

        # 文生图
        image_prompt = f'请根据以下描述生成一张清晰、写实的图片： "{listening_text}"'
        init = generate_image(image_prompt, "文字, 丑陋, 模糊")
        task_id = (init.get("output") or {}).get("task_id")
        if not task_id:
            raise HTTPException(status_code=500, detail="文生图任务未返回 task_id")

        img_url = await _poll_image_task(task_id)
        if not img_url:
            raise HTTPException(status_code=500, detail="文生图任务失败或超时")

        oss_img_url = url_without_course(img_url) or img_url
        # 下载并本地保存为 asset
        img_resp = requests.get(oss_img_url, timeout=60)
        if not img_resp.ok:
            raise HTTPException(status_code=500, detail="下载图片失败")
        img_bytes = img_resp.content
        img_mime = img_resp.headers.get("Content-Type", "image/jpeg").split(";")[0]
        image_public_url, image_rel, image_size, w, h, img_sha = save_image_bytes(img_bytes, img_mime)

        generated_items.append({
            "item_number": idx + 1,
            "keyword": keyword,
            "listening_text": listening_text,
            "image_public_url": image_public_url,   # 保存后的对外 URL
            "image_rel": image_rel,
            "image_mime": img_mime,
            "image_size": image_size,
            "image_w": w,
            "image_h": h,
            "image_sha": img_sha,
            "image_prompt": image_prompt,
            "source_url": oss_img_url
        })

    # 2) 组合听力文本 -> 一条合成音频（与前端一致）
    combined_text = "； ".join([f'{it["item_number"]}：{it["listening_text"]}' for it in generated_items])
    audio_temp_url = generate_voice(combined_text)
    if not audio_temp_url:
        raise HTTPException(status_code=500, detail="生成聚合语音失败")

    # 下载并保存音频为 asset
    audio_resp = requests.get(audio_temp_url, timeout=60)
    if not audio_resp.ok:
        raise HTTPException(status_code=500, detail="下载聚合音频失败")
    audio_bytes = audio_resp.content
    audio_mime = audio_resp.headers.get("Content-Type", "audio/mpeg").split(";")[0]
    audio_public_url, audio_rel, audio_size, audio_dur_ms, audio_sha = save_audio_bytes(audio_bytes, audio_mime)

    # 3) 生成乱序图片映射（A~F）
    labels = ["A", "B", "C", "D", "E", "F"][:len(generated_items)]
    original_urls = [it["image_public_url"] for it in generated_items]
    import random
    shuffled_urls = original_urls[:]
    random.shuffle(shuffled_urls)
    shuffled_images = {labels[i]: shuffled_urls[i] for i in range(len(shuffled_urls))}

    # 4) 计算答案映射：item_number -> label
    answers = {}
    for it in generated_items:
        idx = shuffled_urls.index(it["image_public_url"])
        answers[str(it["item_number"])] = labels[idx]

    # 5) 事务落库（exercise + listening_detail + asset + matching_pool_item + matching_pair）
    try:
        with _db() as conn:
            with conn.cursor() as cur:
                # 5.1 exercise
                cur.execute("""
                    INSERT INTO content.exercise
                      (skill, format, title, stem_text, lang, hsk_level, difficulty, points)
                    VALUES
                      ('listening','picture_match',
                       '听录音·看图配对',
                       '请先听聚合录音（1~N），再把每条描述与正确图片配对。',
                       %s, %s, %s, 1.0)
                    RETURNING id
                """, (body.lang, body.hskLevel, body.difficulty))
                exercise_id = cur.fetchone()[0]

                # 5.2 listening_detail（保存聚合转写，方便前端或阅卷）
                cur.execute("""
                    INSERT INTO content.listening_detail
                      (exercise_id, transcript_text, show_transcript, meta)
                    VALUES
                      (%s, %s, FALSE,
                       jsonb_build_object('items', %s))
                """, (exercise_id, combined_text,
                      json.dumps([{"item_number": it["item_number"],
                                   "keyword": it["keyword"],
                                   "text": it["listening_text"]} for it in generated_items], ensure_ascii=False)))

                # 5.3 asset: audio（并挂到 exercise_asset role=audio）
                cur.execute("""
                    INSERT INTO content.asset
                      (media_kind, url, file_path, mime_type, size_bytes, duration_ms, checksum_sha256, meta)
                    VALUES
                      ('audio', %s, %s, %s, %s, %s, %s,
                       jsonb_build_object('source_url', %s))
                    RETURNING id
                """, (audio_public_url, audio_rel, audio_mime, audio_size, audio_dur_ms, audio_sha, audio_temp_url))
                audio_asset_id = cur.fetchone()[0]

                cur.execute("""
                    INSERT INTO content.exercise_asset(exercise_id, asset_id, role, position)
                    VALUES (%s, %s, 'audio', 1)
                """, (exercise_id, audio_asset_id))

                # 5.4 右列（图片）先插 asset，再落 matching_pool_item(side='R')
                right_item_ids = []   # 按 shuffled 顺序建右列，便于前端直接展示
                for i, label in enumerate(labels):
                    url = shuffled_images[label]
                    # 找到对应 generated item 以取 meta
                    src = next(it for it in generated_items if it["image_public_url"] == url)

                    # 右列图片已保存过，不必再插 asset；但如需在池中也记录 asset_id，可再查一次：
                    # 这里为了严谨，我们重映射出该图片在 content.asset 的记录：按 file_path+sha 唯一
                    cur.execute("""
                        SELECT id FROM content.asset WHERE file_path = %s AND checksum_sha256 = %s
                    """, (src["image_rel"], src["image_sha"]))
                    row = cur.fetchone()
                    if not row:
                        # 极端情况：若找不到，则补插一条（正常不会发生）
                        cur.execute("""
                            INSERT INTO content.asset
                              (media_kind, url, file_path, mime_type, size_bytes, width, height, checksum_sha256, meta)
                            VALUES
                              ('image', %s, %s, %s, %s, %s, %s, %s,
                               jsonb_build_object('prompt', %s, 'source_url', %s))
                            RETURNING id
                        """, (src["image_public_url"], src["image_rel"], src["image_mime"],
                              src["image_size"], src["image_w"], src["image_h"], src["image_sha"],
                              src["image_prompt"], src["source_url"]))
                        asset_id = cur.fetchone()[0]
                    else:
                        asset_id = row[0]

                    cur.execute("""
                        INSERT INTO content.matching_pool_item
                          (exercise_id, side, text, asset_id, order_no, extra)
                        VALUES
                          (%s, 'R', NULL, %s, %s, jsonb_build_object('label', %s))
                        RETURNING id
                    """, (exercise_id, asset_id, i + 1, label))
                    right_item_ids.append(cur.fetchone()[0])

                # 5.5 左列（文本 1~N），保持与 generated_items 的自然顺序
                left_item_ids = []
                for it in generated_items:
                    cur.execute("""
                        INSERT INTO content.matching_pool_item
                          (exercise_id, side, text, asset_id, order_no, extra)
                        VALUES
                          (%s, 'L', %s, NULL, %s, jsonb_build_object('item_number', %s, 'keyword', %s))
                        RETURNING id
                    """, (exercise_id, it["listening_text"], it["item_number"], it["item_number"], it["keyword"]))
                    left_item_ids.append(cur.fetchone()[0])

                # 5.6 建立正确配对：左 i -> 正确的右（根据 answers 映射到 label，再定位 right_item_ids 下标）
                for it in generated_items:
                    label = answers[str(it["item_number"])]
                    ridx = labels.index(label)              # 在 shuffled 右列中的位置
                    left_id = left_item_ids[it["item_number"] - 1]
                    right_id = right_item_ids[ridx]
                    cur.execute("""
                        INSERT INTO content.matching_pair(exercise_id, left_item_id, right_item_id)
                        VALUES (%s, %s, %s)
                    """, (exercise_id, left_id, right_id))

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB error: {e}")

    # 6) 返回给前端（结构与前端 JS 的 finalQuestionSet 对齐）
    return MatchResp(
        question_type="听录音·看图配对",
        hsk_level=body.hskLevel,
        shuffled_images=shuffled_images,
        items=[{"item_number": it["item_number"],
                "listening_text": it["listening_text"],
                "image_url": it["image_public_url"]} for it in generated_items],
        combined_audio={"text": combined_text, "url": audio_public_url},
        answers=answers,
        exercise_id=str(exercise_id),
    )

#听录音对话问答（选择）

class DialogueBundleReq(BaseModel):
    keyword: str
    hskLevel: int = Field(..., ge=1, le=6)
    numQuestions: int = Field(2, ge=1, le=10)  # 你要生成几个单选题
    lang: str = "zh-CN"
    difficulty: int = Field(2, ge=1, le=5)
    show_transcript: bool = False
    saveToDB: bool = True                      # 默认直接落库

class ChoiceOption(BaseModel):
    id: str
    content: str

class SingleChoiceItem(BaseModel):
    stem: str
    options: List[ChoiceOption]   # 4 项（A~D）
    correctIndex: int             # 0..3

class DialogueBundleResp(BaseModel):
    group_id: str
    context_exercise_id: str
    dialogue_text: str
    audio_url: str
    questions: List[SingleChoiceItem]
    question_exercise_ids: List[str]

@router.post("/api/generate/dialogue-single-choice-bundle", response_model=DialogueBundleResp)
async def generate_dialogue_single_choice_bundle(body: DialogueBundleReq):
    """
    生成一段对话 + 单选题组（N 道）。音频只在“对话载体题”绑定一次；所有小题为 single_choice，不再绑音频。
    """

    # 1) 生成对话文本（不超过2人，>=5轮，自然口语；只返回文本）
    prompt_dlg = f"""
请围绕关键词“{body.keyword}”设计一个生活化的中文对话，角色不超过2人，对话不少于5轮，
语言风格自然简洁，难度符合HSK{body.hskLevel}级水平。
不要加入任何解释说明，仅返回对话文本。
""".strip()
    dialogue_text = generate_from_llm(prompt_dlg).strip()
    if not dialogue_text:
        raise HTTPException(status_code=500, detail="生成失败：无对话文本")

    # 2) 生成整段语音（只此一条）
    tts_url = generate_voice(dialogue_text)
    if not tts_url:
        raise HTTPException(status_code=500, detail="语音生成失败，未能获取URL")

    # 下载并保存到本地 asset（与你现有保存函数与媒体布局一致）
    resp = requests.get(tts_url, timeout=60)
    if not resp.ok:
        raise HTTPException(status_code=500, detail="下载音频失败")
    audio_public_url, audio_rel, audio_size, audio_dur_ms, audio_sha = save_audio_bytes(
        resp.content, resp.headers.get("Content-Type", "audio/mpeg").split(";")[0]
    )

    # 3) 批量生成 N 道单选题（A~D，correctIndex 为 0..3）
    #    为避免重复，逐题把已有题干传给 LLM 让它避免重复语义
    questions: List[SingleChoiceItem] = []
    for i in range(body.numQuestions):
        existing_q = "\n".join([f'问题{idx+1}: {q.stem}' for idx, q in enumerate(questions)])
        avoid_section = f"请避免与以下问题重复：\n{existing_q}" if existing_q else ""

        q_prompt = f"""
        下面是一段中文对话，请基于这段对话生成一个**单选题**，包含题干与4个选项（A~D），以及正确答案索引（0..3）。
        要求：题干聚焦关键信息，四个选项语义清晰，难度与HSK{body.hskLevel}水平一致。
        对话内容：
        {dialogue_text}
        {avoid_section}

        严格按如下 JSON 返回，不要多余文字：
        {{
        "question": "题干文本",
        "options": [
            {{ "id": "A", "content": "选项A内容" }},
            {{ "id": "B", "content": "选项B内容" }},
            {{ "id": "C", "content": "选项C内容" }},
            {{ "id": "D", "content": "选项D内容" }}
        ],
        "correctIndex": 0
        }}
        """.strip()

        raw = generate_from_llm(q_prompt).strip()
        try:
            js = json.loads(raw)
            opts = js.get("options", [])
            if not isinstance(opts, list) or len(opts) != 4:
                raise ValueError("必须返回4个选项")
            item = SingleChoiceItem(
                stem=str(js["question"]).strip(),
                options=[ChoiceOption(id=str(o["id"]), content=str(o["content"]).strip()) for o in opts],
                correctIndex=int(js["correctIndex"])
            )
            if item.correctIndex not in (0,1,2,3):
                raise ValueError("correctIndex 需在 0..3")
            if any((o.id not in ("A","B","C","D") or not o.content) for o in item.options):
                raise ValueError("选项必须是 A~D 且有内容")
            questions.append(item)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"生成单选题失败: {e}")

    # 4) 按需落库（只在载体题绑定音频；小题不再绑音频）
    group_id = str(uuid.uuid4())
    context_id = None
    question_ids: List[str] = []

    if body.saveToDB:
        try:
            with _db() as conn:
                with conn.cursor() as cur:
                    # 4.1 先登记音频 asset
                    cur.execute("""
                        INSERT INTO content.asset
                          (media_kind, url, file_path, mime_type, size_bytes, duration_ms, checksum_sha256)
                        VALUES
                          ('audio', %s, %s, %s, %s, %s, %s)
                        RETURNING id
                    """, (audio_public_url, audio_rel, "audio/mpeg", audio_size, audio_dur_ms, audio_sha))
                    audio_asset_id = cur.fetchone()[0]

                    # 4.2 “对话载体题”（只负责承载音频与对话语境）
                    cur.execute("""
                        INSERT INTO content.exercise
                          (skill, format, title, stem_text, lang, hsk_level, difficulty, points, extra)
                        VALUES
                          ('listening','dialog_choice',
                           '请听对话',
                           '请听以下对话，然后回答后面的选择题。',
                           %s, %s, %s, 1.0,
                           jsonb_build_object('dialogue_group_id', %s))
                        RETURNING id
                    """, (body.lang, body.hskLevel, body.difficulty, group_id))
                    context_id = cur.fetchone()[0]

                    # 4.3 对话转写（可选择是否对学生展示）
                    cur.execute("""
                        INSERT INTO content.listening_detail
                          (exercise_id, transcript_text, show_transcript, meta)
                        VALUES
                          (%s, %s, %s, jsonb_build_object('keyword', %s))
                    """, (context_id, dialogue_text, body.show_transcript, body.keyword))

                    # 4.4 绑定音频（只在载体题）
                    cur.execute("""
                        INSERT INTO content.exercise_asset(exercise_id, asset_id, role, position)
                        VALUES (%s, %s, 'audio', 1)
                    """, (context_id, audio_asset_id))

                    # 4.5 建 N 条单选题（不绑定音频，仅写选项与答案，挂同一个 group_id）
                    for q in questions:
                        cur.execute("""
                            INSERT INTO content.exercise
                              (skill, format, title, stem_text, lang, hsk_level, difficulty, points, extra)
                            VALUES
                              ('listening','dialog_choice',
                               '对话理解', %s,
                               %s, %s, %s, 1.0,
                               jsonb_build_object('dialogue_group_id', %s))
                            RETURNING id
                        """, (q.stem, body.lang, body.hskLevel, body.difficulty, group_id))
                        qid = cur.fetchone()[0]
                        question_ids.append(str(qid))

                        labels = ["A","B","C","D"]
                        opt_ids = []
                        for order_no, (L, opt) in enumerate(zip(labels, q.options), start=1):
                            cur.execute("""
                                INSERT INTO content.option(exercise_id, label, text, order_no)
                                VALUES (%s, %s, %s, %s)
                                RETURNING id
                            """, (qid, L, opt.content, order_no))
                            opt_ids.append(cur.fetchone()[0])

                        # 正确答案
                        correct_opt_id = opt_ids[q.correctIndex]
                        cur.execute("""
                            INSERT INTO content.answer_key(exercise_id, option_id, is_correct, score)
                            VALUES (%s, %s, TRUE, 1.0)
                        """, (qid, correct_opt_id))
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"DB error: {e}")

    # 5) 返回给前端（既可直接渲染，也可用于继续补题）
    return DialogueBundleResp(
        group_id=group_id,
        context_exercise_id=str(context_id) if context_id else "",
        dialogue_text=dialogue_text,
        audio_url=audio_public_url,
        questions=questions,
        question_exercise_ids=question_ids
    )

class ListenSentTFReq(BaseModel):
    keyword: str
    hskLevel: int = Field(..., ge=1, le=6)
    lang: str = "zh-CN"
    difficulty: int = Field(2, ge=1, le=5)

class ListenSentTFResp(BaseModel):
    question_type: str
    hsk_level: int
    listening_text: str
    question: str
    correct_answer: str
    audio_url: str
    exercise_id: str


@router.post("/api/generate/listen-sentence-tf", response_model=ListenSentTFResp)
async def generate_listen_sentence_tf(body: ListenSentTFReq):
    """生成【听录音·句子理解判断题】"""

    hskExplain = HSK_LEVEL_DESCRIPTIONS.get(body.hskLevel, "无特定描述")

    prompt = f"""
请生成一段中文文本（1-2句），主题必须包含关键词“{body.keyword}”，
难度符合HSK{body.hskLevel}（{hskExplain}），
生成后再设计一个判断题，可以与原文一致（正确）或相反（错误）。
返回严格JSON：
{{
  "generated_text": "...",
  "question": "...",
  "answer": "True/False"
}}
""".strip()

    raw = generate_from_llm(prompt).strip()
    try:
        js = json.loads(raw)
        listening_text = js["generated_text"].strip()
        question = js["question"].strip()
        answer = str(js["answer"]).lower() in ("true", "正确")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"解析失败: {e}")

    # 2) 生成音频
    audio_temp_url = generate_voice(listening_text)
    audio_resp = requests.get(audio_temp_url, timeout=30)
    if not audio_resp.ok:
        raise HTTPException(status_code=500, detail="下载音频失败")
    audio_bytes = audio_resp.content
    audio_mime = audio_resp.headers.get("Content-Type", "audio/mpeg").split(";")[0]
    audio_public_url, audio_rel, audio_size, audio_dur_ms, audio_sha = save_audio_bytes(audio_bytes, audio_mime)

    # 3) 入库
    try:
        with _db() as conn:
            with conn.cursor() as cur:
                # asset: audio
                cur.execute("""
                    INSERT INTO content.asset
                      (media_kind, url, file_path, mime_type, size_bytes, duration_ms, checksum_sha256, meta)
                    VALUES ('audio', %s, %s, %s, %s, %s, %s,
                            jsonb_build_object('source_url', %s))
                    RETURNING id
                """, (audio_public_url, audio_rel, audio_mime, audio_size, audio_dur_ms, audio_sha, audio_temp_url))
                audio_asset_id = cur.fetchone()[0]

                # exercise
                cur.execute("""
                    INSERT INTO content.exercise
                      (skill, format, title, stem_text, lang, hsk_level, difficulty, points)
                    VALUES ('listening','sentence_tf',
                            '听录音·句子理解判断',
                            %s, %s, %s, %s, 1.0)
                    RETURNING id
                """, ("请听录音，再判断下面的句子是否正确。", body.lang, body.hskLevel, body.difficulty))
                exercise_id = cur.fetchone()[0]

                # detail
                cur.execute("""
                    INSERT INTO content.exercise_tf_detail
                      (exercise_id, correct_is_true, explanation, transcript_text, core_keyword, meta)
                    VALUES (%s, %s, %s, %s, %s,
                            jsonb_build_object('statement', %s))
                """, (
                    exercise_id, answer,
                    "与录音内容一致为正确，不一致为错误。",
                    listening_text, body.keyword, question
                ))

                # 关联音频
                cur.execute("""
                    INSERT INTO content.exercise_asset
                      (exercise_id, asset_id, role, position)
                    VALUES (%s, %s, 'audio', 1)
                """, (exercise_id, audio_asset_id))

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB error: {e}")

    return ListenSentTFResp(
        question_type="听录音·句子理解判断",
        hsk_level=body.hskLevel,
        listening_text=listening_text,
        question=question,
        correct_answer="正确" if answer else "错误",
        audio_url=audio_public_url,
        exercise_id=str(exercise_id),
    )

class ListeningPassageReq(BaseModel):
    hskLevel: int = Field(..., ge=1, le=6)
    topic: str
    textLength: int = Field(300, ge=80, le=1200)   # 文章字数
    numQuestions: int = Field(2, ge=1, le=10)      # 生成题目数量
    lang: str = "zh-CN"
    difficulty: int = Field(3, ge=1, le=5)
    show_transcript: bool = False                  # 是否在前端显示转写

class LPChoiceOption(BaseModel):
    id: str
    content: str

class LPQuestionItem(BaseModel):
    stem: str
    stem_audio_url: str
    options: List[LPChoiceOption]
    correctIndex: int
    exercise_id: str = ""

class ListeningPassageResp(BaseModel):
    context_exercise_id: str
    passage_text: str
    passage_audio_url: str
    questions: List[LPQuestionItem]


@router.post("/api/generate/listening-passage-choice-bundle", response_model=ListeningPassageResp)
async def generate_listening_passage_choice_bundle(body: ListeningPassageReq):
    """
    生成一段文章 + N 道单选题（每道题干配 TTS 音频），并全部落库。
    载体题(skill='listening', format='paragraph_choice')承载文章文本与文章音频；
    每个子题也是 paragraph_choice，额外绑定各自的题干音频。
    """

    # 1) 生成文章
    hskExplain = HSK_LEVEL_DESCRIPTIONS.get(body.hskLevel, "无特定描述")
    prompt_passage = f"""
请根据以下要求生成一段中文文章：
- 主题：{body.topic}
- HSK 等级：HSK{body.hskLevel}（{hskExplain}）
- 字数：约 {body.textLength} 字（可±10%）
- 风格：句子通顺、逻辑自然、积极向上，可分为多个自然段；仅返回正文，不要任何解释或标题。
""".strip()
    passage_text = generate_from_llm(prompt_passage).strip()
    if not passage_text:
        raise HTTPException(status_code=500, detail="文章生成失败")

    # 2) 为整段文章生成 TTS 并保存为 asset
    passage_tts_url = generate_voice(passage_text)
    resp = requests.get(passage_tts_url, timeout=60)
    if not resp.ok:
        raise HTTPException(status_code=500, detail="下载文章音频失败")
    passage_audio_public_url, passage_audio_rel, passage_audio_size, passage_audio_dur_ms, passage_audio_sha = \
        save_audio_bytes(resp.content, resp.headers.get("Content-Type", "audio/mpeg").split(";")[0])

    # 3) 生成 N 道单选题（避免重复）
    questions: List[LPQuestionItem] = []
    for i in range(body.numQuestions):
        existed = "\n".join([f'问题{idx+1}: {q.stem}' for idx, q in enumerate(questions)])
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
        raw = generate_from_llm(q_prompt).strip()
        try:
            js = json.loads(raw)
            opts = js.get("options", [])
            if not isinstance(opts, list) or len(opts) != 4:
                raise ValueError("必须返回4个选项")
            item = LPQuestionItem(
                stem=str(js["question"]).strip(),
                stem_audio_url="",  # 占位，稍后生成
                options=[LPChoiceOption(id=lab, content=str(opts[i]["content"]).strip())
                         for i, lab in enumerate(["A","B","C","D"])],
                correctIndex=int(js["correctIndex"])
            )
            if item.correctIndex not in (0,1,2,3):
                raise ValueError("correctIndex 需在 0..3")
            questions.append(item)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"生成问题失败: {e}")

    # 4) 落库（文章载体题 + 文章音频 + passage_detail + listening_detail）
    try:
        with _db() as conn:
            with conn.cursor() as cur:
                # 4.1 文章音频 asset
                cur.execute("""
                    INSERT INTO content.asset
                      (media_kind, url, file_path, mime_type, size_bytes, duration_ms, checksum_sha256, meta)
                    VALUES ('audio', %s, %s, %s, %s, %s, %s, jsonb_build_object('source_url', %s))
                    RETURNING id
                """, (passage_audio_public_url, passage_audio_rel, "audio/mpeg",
                      passage_audio_size, passage_audio_dur_ms, passage_audio_sha, passage_tts_url))
                passage_audio_asset_id = cur.fetchone()[0]

                # 4.2 载体题（承载文章与文章音频）
                cur.execute("""
                    INSERT INTO content.exercise
                      (skill, format, title, stem_text, lang, hsk_level, difficulty, points)
                    VALUES ('listening','paragraph_choice',
                            '听力·段落理解',
                            '请听下面的文章，然后回答后面的选择题。',
                            %s, %s, %s, 1.0)
                    RETURNING id
                """, (body.lang, body.hskLevel, body.difficulty))
                context_exercise_id = cur.fetchone()[0]

                # 4.3 passage_detail（保存文章）
                cur.execute("""
                    INSERT INTO content.passage_detail
                      (exercise_id, passage_title, passage_text, passage_lang, meta)
                    VALUES (%s, %s, %s, %s, jsonb_build_object('topic', %s, 'length_hint', %s))
                """, (context_exercise_id, body.topic, passage_text, body.lang, body.topic, body.textLength))

                # 4.4 listening_detail（保存转写/是否展示）
                cur.execute("""
                    INSERT INTO content.listening_detail
                      (exercise_id, transcript_text, show_transcript, meta)
                    VALUES (%s, %s, %s, jsonb_build_object('type', 'passage_audio'))
                """, (context_exercise_id, passage_text, body.show_transcript))

                # 4.5 关联文章音频
                cur.execute("""
                    INSERT INTO content.exercise_asset(exercise_id, asset_id, role, position)
                    VALUES (%s, %s, 'audio', 1)
                """, (context_exercise_id, passage_audio_asset_id))

                # 5) 为每道题生成题干音频，建子题 + 选项 + 正确答案 + 音频 asset/关联
                for idx, q in enumerate(questions, start=1):
                    # 5.1 题干音频
                    stem_tts_url = generate_voice(q.stem)
                    r = requests.get(stem_tts_url, timeout=60)
                    if not r.ok:
                        raise RuntimeError("下载题干音频失败")
                    stem_audio_public_url, stem_audio_rel, stem_audio_size, stem_audio_dur_ms, stem_audio_sha = \
                        save_audio_bytes(r.content, r.headers.get("Content-Type", "audio/mpeg").split(";")[0])

                    # 5.2 题干音频 asset
                    cur.execute("""
                        INSERT INTO content.asset
                          (media_kind, url, file_path, mime_type, size_bytes, duration_ms, checksum_sha256, meta)
                        VALUES ('audio', %s, %s, %s, %s, %s, %s, jsonb_build_object('source_url', %s))
                        RETURNING id
                    """, (stem_audio_public_url, stem_audio_rel, "audio/mpeg",
                          stem_audio_size, stem_audio_dur_ms, stem_audio_sha, stem_tts_url))
                    stem_audio_asset_id = cur.fetchone()[0]

                    # 5.3 子题（单选）
                    cur.execute("""
                        INSERT INTO content.exercise
                          (skill, format, title, stem_text, lang, hsk_level, difficulty, points, extra)
                        VALUES ('listening','paragraph_choice',
                                '段落理解·单选', %s,
                                %s, %s, %s, 1.0,
                                jsonb_build_object('context_exercise_id', %s, 'order_in_group', %s))
                        RETURNING id
                    """, (q.stem, body.lang, body.hskLevel, body.difficulty, context_exercise_id, idx))
                    q_exercise_id = cur.fetchone()[0]
                    q.exercise_id = str(q_exercise_id)
                    q.stem_audio_url = stem_audio_public_url

                    # 5.4 关联题干音频
                    cur.execute("""
                        INSERT INTO content.exercise_asset(exercise_id, asset_id, role, position)
                        VALUES (%s, %s, 'audio', 1)
                    """, (q_exercise_id, stem_audio_asset_id))

                    # 5.5 选项
                    labels = ["A","B","C","D"]
                    opt_ids = []
                    for order_no, (lab, opt) in enumerate(zip(labels, q.options), start=1):
                        cur.execute("""
                            INSERT INTO content.option(exercise_id, label, text, order_no)
                            VALUES (%s, %s, %s, %s)
                            RETURNING id
                        """, (q_exercise_id, lab, opt.content, order_no))
                        opt_ids.append(cur.fetchone()[0])

                    # 5.6 正确答案
                    correct_opt_id = opt_ids[q.correctIndex]
                    cur.execute("""
                        INSERT INTO content.answer_key(exercise_id, option_id, is_correct, score)
                        VALUES (%s, %s, TRUE, 1.0)
                    """, (q_exercise_id, correct_opt_id))

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB error: {e}")

    return ListeningPassageResp(
        context_exercise_id=str(context_exercise_id),
        passage_text=passage_text,
        passage_audio_url=passage_audio_public_url,
        questions=questions
    )




class ListenSentChoiceReq(BaseModel):
    keyword: str
    hskLevel: int = Field(..., ge=1, le=6)
    lang: str = "zh-CN"
    difficulty: int = Field(1, ge=1, le=5)
    show_transcript: bool = False                 # 是否在前端显示原句转写
    join_text: str = "{sentence}。 问：{question}"  # 可自定义拼接模板


class ListenSentChoiceResp(BaseModel):
    question_type: str
    hsk_level: int
    sentence_text: str          # 原句（纯文本）
    question: str               # 问：题干
    options: Dict[str, str]     # {"A": "...", "B": "...", "C": "..."}
    correct_answer: str         # "A"/"B"/"C"
    audio_url: str              # 句子+问题 合成的一条音频
    exercise_id: str


@router.post("/api/generate/listen-sentence-choice",
             response_model=ListenSentChoiceResp)
async def generate_listen_sentence_choice(body: ListenSentChoiceReq):
    """
    听力·句子理解（3选1）：先用LLM生成「句子 + 题目 + 选项 + 答案」，
    然后把「句子 + 问题」拼成一段文本，再做 TTS，只生成一条音频。
    """

    # 1) 让 LLM 严格返回 JSON
    hskExplain = HSK_LEVEL_DESCRIPTIONS.get(body.hskLevel, "无特定描述")
    prompt = f"""
请为“听力·句子理解选择题（3选1）”生成内容，并严格只返回 JSON（可直接 JSON.parse）：
- 依据关键词：{body.keyword}
- HSK 等级：HSK{body.hskLevel}（{hskExplain}）
- 先写 1~2 句自然、积极向上的中文（用于听力）；再基于该句生成 1 道单选题（A/B/C）
- 选项互斥且有干扰性；仅 1 个正确；题干需围绕句子信息

JSON：
{{
  "generated_text": "……一到两句原句……",
  "question": "……题干……",
  "options": ["……A……","……B……","……C……"],
  "answer": "A"
}}
（不要任何多余文本、注释或引号变体）
""".strip()

    raw = generate_from_llm(prompt).strip()
    try:
        js = json.loads(raw)
        sentence_text = str(js["generated_text"]).strip()
        question_core = str(js["question"]).strip()
        options_list: List[str] = [str(x).strip() for x in js["options"]]
        answer_letter = str(js["answer"]).strip().upper()
        if len(options_list) != 3 or answer_letter not in ("A", "B", "C"):
            raise ValueError("options 必须3项且 answer ∈ {A,B,C}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM 返回解析失败: {e}")

    # 2) 拼接“句子 + 问题”，再做 TTS（只生成一条音频）
    display_question = f"问：{question_core}"
    tts_text = body.join_text.format(sentence=sentence_text, question=question_core)
    # 例："{sentence}。 问：{question}" -> "......。 问：......"

    audio_temp_url = generate_voice(tts_text)
    resp = requests.get(audio_temp_url, timeout=45)
    if not resp.ok:
        raise HTTPException(status_code=500, detail="下载合成音频失败")
    mime = resp.headers.get("Content-Type", "audio/mpeg").split(";")[0]
    audio_public_url, audio_rel, audio_size, audio_dur_ms, audio_sha = \
        save_audio_bytes(resp.content, mime)

    # 3) 入库（exercise + listening_detail + option + answer_key + asset + exercise_asset）
    try:
        with _db() as conn:
            with conn.cursor() as cur:
                # 3.1 保存音频 asset
                cur.execute("""
                    INSERT INTO content.asset
                      (media_kind, url, file_path, mime_type, size_bytes, duration_ms, checksum_sha256, meta)
                    VALUES ('audio', %s, %s, %s, %s, %s, %s,
                            jsonb_build_object('source_url', %s, 'compose', 'sentence+question'))
                    RETURNING id
                """, (audio_public_url, audio_rel, mime, audio_size, audio_dur_ms, audio_sha, audio_temp_url))
                audio_asset_id = cur.fetchone()[0]

                # 3.2 建题（题干直接写“问：xxx”）
                cur.execute("""
                    INSERT INTO content.exercise
                      (skill, format, title, stem_text, lang, hsk_level, difficulty, points, extra)
                    VALUES ('listening','sentence_choice',
                            '听力·句子理解（单选）',
                            %s, %s, %s, %s, 1.0,
                            jsonb_build_object('audio_contains_question', TRUE,
                                               'play_audio_then_question', TRUE))
                    RETURNING id
                """, (display_question, body.lang, body.hskLevel, body.difficulty))
                exercise_id = cur.fetchone()[0]

                # 3.3 听力文本（存原句；meta 里带上 question 与合成全文，便于复用）
                cur.execute("""
                    INSERT INTO content.listening_detail
                      (exercise_id, transcript_text, show_transcript, meta)
                    VALUES (%s, %s, %s,
                            jsonb_build_object('question', %s, 'tts_text', %s))
                """, (exercise_id, sentence_text, body.show_transcript, question_core, tts_text))

                # 3.4 绑定音频
                cur.execute("""
                    INSERT INTO content.exercise_asset(exercise_id, asset_id, role, position)
                    VALUES (%s, %s, 'audio', 1)
                """, (exercise_id, audio_asset_id))

                # 3.5 选项与答案
                labels = ["A", "B", "C"]
                option_ids: Dict[str, str] = {}
                for idx, (lab, text) in enumerate(zip(labels, options_list), start=1):
                    cur.execute("""
                        INSERT INTO content.option(exercise_id, label, text, order_no)
                        VALUES (%s, %s, %s, %s)
                        RETURNING id
                    """, (exercise_id, lab, text, idx))
                    option_ids[lab] = cur.fetchone()[0]

                cur.execute("""
                    INSERT INTO content.answer_key(exercise_id, option_id, is_correct, score)
                    VALUES (%s, %s, TRUE, 1.0)
                """, (exercise_id, option_ids[answer_letter]))

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB error: {e}")

    return ListenSentChoiceResp(
        question_type="听力·句子理解（单选，合成一条音频）",
        hsk_level=body.hskLevel,
        sentence_text=sentence_text,
        question=display_question,                 # “问：xxx”
        options={"A": options_list[0], "B": options_list[1], "C": options_list[2]},
        correct_answer=answer_letter,
        audio_url=audio_public_url,                # 句子+问题 的合成音频
        exercise_id=str(exercise_id),
    )


class ReadingJudgeReq(BaseModel):
    keyword: str
    hskLevel: int = Field(..., ge=1, le=6)
    isCorrect: bool = True
    textType: str = "一句话"
    lang: str = "zh-CN"
    difficulty: int = Field(2, ge=1, le=5)
    seed: Optional[int] = None

class ReadingJudgeResp(BaseModel):
    question_type: str
    hsk_level: int
    display_text: str
    image_url: str
    correct_answer: str
    exercise_id: str


@router.post("/api/generate/reading-image-tf", response_model=ReadingJudgeResp)
async def generate_reading_image_tf(body: ReadingJudgeReq):
    """
    生成【阅读·看图判断】并落库
    流程：
    1. 根据关键词和 HSK 等级生成一段描述文本（displayText）
    2. 根据 isCorrect 判断，如果为 True，则用 displayText 生成图片；如果为 False，则用另一个 AI prompt 生成一个完全不相关的描述，再用该描述生成图片。
    3. 将生成的图片保存到本地 asset。
    4. 将所有数据（题目、判断细节、图片 asset、关联关系）以事务形式写入数据库。
    """
    hskExplain = HSK_LEVEL_DESCRIPTIONS.get(body.hskLevel, "无特定描述")
    textTypeExplain = TEXT_TYPE_INSTRUCTIONS.get(body.textType, "生成一个简单的句子")

    # 1) 生成描述文本 (displayText)
    BASE_TEXT_PROMPT = f"""
作为一名顶尖的中文教学内容（CSL）设计师，请为“看图判断”题型创作一个高质量的中文词语或句子。
- **核心词汇**: 必须是 `{body.keyword}` 或其直接相关的表达。
- **目标等级**: HSK {body.hskLevel} ({hskExplain})
- **指定形式**: {textTypeExplain}
- **要求**: 文本必须能够被清晰、无歧义地用一张图片表现出来。
- **输出格式**: 请直接输出最终生成的文本，只需要图片的内容，不需要任何多余的解释。
""".strip()
    displayText = generate_from_llm(BASE_TEXT_PROMPT).strip()
    if not displayText:
        raise HTTPException(status_code=500, detail="AI生成基础文本失败")

    # 2) 根据 isCorrect 决定用于生成图片的描述文本
    imageDescriptionText = ""
    final_answer = "正确" if body.isCorrect else "错误"

    if body.isCorrect:
        imageDescriptionText = displayText
    else:
        WRONG_PROMPT_TEMPLATE = f"""
作为一名严谨的中文试题设计师，你的任务是为【{displayText}】 创作一个用于生成【不匹配图片】的描述文本。
- **目标等级**: HSK {body.hskLevel} ({hskExplain})
- **指定形式**: {textTypeExplain}

- **核心要求**:
  1. **主题和场景必须完全不同**: 新描述的人物、地点、事件和物品必须与原始文本【完全无关】。
  2. **难度对等**: 新描述的复杂度应与原始文本保持在同一个 HSK 等级水平。
  3. **确保可被清晰可视化**: 新描述必须能够被轻松地、无歧义地转换成一张图片。

- --- 输出要求 ---
请直接输出你创作的那个全新的、用于生成不匹配图片的描述文本，不要包含任何多余的解释。
""".strip()
        wrongText = generate_from_llm(WRONG_PROMPT_TEMPLATE).strip()
        if not wrongText:
            raise HTTPException(status_code=500, detail="AI生成干扰项图片描述失败")
        imageDescriptionText = wrongText

    # 3) 文生图并保存本地
    image_prompt = f'请根据以下描述生成一张清晰、写实的图片，画面中不要出现任何文字： "{imageDescriptionText}"'
    init = generate_image(image_prompt, "文字, 丑陋, 模糊")
    task_id = init.get("output", {}).get("task_id")
    if not task_id:
        raise HTTPException(status_code=500, detail="文生图任务未返回 task_id")

    image_url = await _poll_image_task(task_id)
    if not image_url:
        raise HTTPException(status_code=500, detail="文生图任务失败或超时")

    # 下载并保存图片
    oss_image_url = url_without_course(image_url) or image_url
    img_resp = requests.get(oss_image_url, timeout=60)
    if not img_resp.ok:
        raise HTTPException(status_code=500, detail="下载图片失败")
    img_bytes = img_resp.content
    img_mime = img_resp.headers.get("Content-Type", "image/jpeg").split(";")[0]
    image_public_url, image_rel, image_size, w, h, img_sha = save_image_bytes(img_bytes, img_mime)

    # 4) 事务入库
    exercise_id = None
    try:
        with _db() as conn:
            with conn.cursor() as cur:
                # asset: image
                cur.execute("""
                    INSERT INTO content.asset
                      (media_kind, url, file_path, mime_type, size_bytes, width, height, checksum_sha256, meta)
                    VALUES
                      ('image', %s, %s, %s, %s, %s, %s, %s,
                        jsonb_build_object('prompt', %s, 'source_url', %s))
                    RETURNING id
                """, (image_public_url, image_rel, img_mime, image_size, w, h, img_sha, image_prompt, oss_image_url))
                image_asset_id = cur.fetchone()[0]

                # exercise
                cur.execute("""
                    INSERT INTO content.exercise
                    (skill, format, title, stem_text, lang, hsk_level, difficulty, points)
                 VALUES
                    ('reading', 'picture_tf',
                    '看图判断',
                    '请看图片，判断下面的句子是否正确。',
                    %s, %s, %s, 1.0)
                    RETURNING id
                """, (body.lang, body.hskLevel, body.difficulty))
                exercise_id = cur.fetchone()[0]

                # detail
                cur.execute("""
                    INSERT INTO content.exercise_tf_detail
                      (exercise_id, correct_is_true, explanation, transcript_text, core_keyword, meta)
                    VALUES
                      (%s, %s, %s, NULL, %s,
                        jsonb_build_object('statement', %s, 'mode', %s))
                """, (
                    exercise_id,
                    body.isCorrect,
                    "图文一致为“正确”，不一致为“错误”。",
                    body.keyword,
                    displayText,
                    "consistent" if body.isCorrect else "inconsistent"
                ))

                # 关联题图
                cur.execute("""
                    INSERT INTO content.exercise_asset
                      (exercise_id, asset_id, role, position)
                    VALUES (%s, %s, 'stem_image', 1)
                """, (exercise_id, image_asset_id))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB error: {e}")

    # 5) 返回
    return ReadingJudgeResp(
        question_type="阅读·看图判断",
        hsk_level=body.hskLevel,
        display_text=displayText,
        image_url=image_public_url,
        correct_answer=final_answer,
        exercise_id=str(exercise_id),
    )


class ReadingMatchReq(BaseModel):
    keywordsList: List[str] = Field(..., min_length=2, max_length=6)
    hskLevel: int = Field(..., ge=1, le=6)
    textTypesList: List[str]
    lang: str = "zh-CN"
    difficulty: int = Field(2, ge=1, le=5)

class ReadingMatchResp(BaseModel):
    question_type: str
    hsk_level: int
    shuffled_images: Dict[str, str]
    reading_items: List[Dict[str, Any]]
    answers: Dict[str, str]
    exercise_id: str


@router.post("/api/generate/reading-picture-matching", response_model=ReadingMatchResp)
async def generate_reading_picture_matching(body: ReadingMatchReq):

    if len(body.keywordsList) != len(body.textTypesList):
        raise HTTPException(status_code=400, detail="keywordsList 与 textTypesList 长度必须一致。")

    generated_items: List[Dict[str, Any]] = []

    # 使用 asyncio.gather 并发执行，提升效率
    async def process_item(index: int, keyword: str, text_type: str):
        hsk_explain = HSK_LEVEL_DESCRIPTIONS.get(str(body.hskLevel), '无特定描述')
        text_type_explain = TEXT_TYPE_INSTRUCTIONS.get(text_type, '生成一个简单的句子')

        # 1. 生成阅读文本
        prompt = f"""
作为一名顶尖的中文教学内容（CSL）设计师，请为“阅读·看图配对”题型创作一段高质量的中文文本。
- **核心词汇**: 文本必须围绕 `{keyword}` 展开。
- **场景要求**: 文本必须描述一个清晰、具体、可以用图像轻松表现的场景或动作。
- **语言水平**: HSK {body.hskLevel} ({hsk_explain})
- **文本形式**: {text_type} ({text_type_explain})
- **输出格式**: 只输出最终文本，不要包含任何额外的标题、解释或标签。
""".strip()
        
        reading_text = generate_from_llm(prompt).strip()
        if not reading_text:
            raise RuntimeError(f"为关键词“{keyword}”生成阅读文本失败")

        # 2. 文生图
        image_prompt = f'请根据以下描述生成一张清晰、写实的图片，画面中不要出现任何文字： "{reading_text}"'
        init = generate_image(image_prompt, "文字, 丑陋, 模糊")
        task_id = (init.get("output") or {}).get("task_id")
        if not task_id:
            raise RuntimeError("文生图任务未返回 task_id")

        img_url = await _poll_image_task(task_id)
        if not img_url:
            raise RuntimeError("文生图任务失败或超时")

        # 3. 下载并保存图片
        oss_img_url = url_without_course(img_url) or img_url
        img_resp = requests.get(oss_img_url, timeout=60)
        if not img_resp.ok:
            raise RuntimeError("下载图片失败")
        img_bytes = img_resp.content
        img_mime = img_resp.headers.get("Content-Type", "image/jpeg").split(";")[0]
        image_public_url, image_rel, image_size, w, h, img_sha = save_image_bytes(img_bytes, img_mime)

        return {
            "keyword": keyword,
            "reading_text": reading_text,
            "image_public_url": image_public_url,
            "image_rel": image_rel,
            "image_mime": img_mime,
            "image_size": image_size,
            "image_w": w,
            "image_h": h,
            "image_sha": img_sha,
            "image_prompt": image_prompt,
            "source_url": oss_img_url
        }

    try:
        tasks = [process_item(i, kw, tt) for i, (kw, tt) in enumerate(zip(body.keywordsList, body.textTypesList))]
        generated_items = await asyncio.gather(*tasks)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))

    # 4. 洗牌和计算答案
    labels = ["A", "B", "C", "D", "E", "F"][:len(generated_items)]
    original_urls = [item["image_public_url"] for item in generated_items]
    shuffled_urls = original_urls[:]
    random.shuffle(shuffled_urls)

    shuffled_images = {labels[i]: shuffled_urls[i] for i in range(len(shuffled_urls))}
    answers = {}
    for i, item in enumerate(generated_items):
        item_number = i + 1
        correct_image_index = shuffled_urls.index(item["image_public_url"])
        answers[str(item_number)] = labels[correct_image_index]

    # 5. 事务落库
    exercise_id = None
    try:
        with _db() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO content.exercise
                      (skill, format, title, stem_text, lang, hsk_level, difficulty, points)
                    VALUES
                      ('reading','picture_match',
                       '阅读·看图配对',
                       '请将左侧的句子与右侧的图片配对。',
                       %s, %s, %s, 1.0)
                    RETURNING id
                """, (body.lang, body.hskLevel, body.difficulty))
                exercise_id = cur.fetchone()[0]

                # 5.1 右列图片 asset + matching_pool_item
                right_item_ids = {}
                for i, label in enumerate(labels):
                    url = shuffled_images[label]
                    src = next(item for item in generated_items if item["image_public_url"] == url)

                    cur.execute("""
                        INSERT INTO content.asset
                          (media_kind, url, file_path, mime_type, size_bytes, width, height, checksum_sha256, meta)
                        VALUES
                          ('image', %s, %s, %s, %s, %s, %s, %s,
                           jsonb_build_object('prompt', %s, 'source_url', %s))
                        RETURNING id
                    """, (src["image_public_url"], src["image_rel"], src["image_mime"],
                          src["image_size"], src["image_w"], src["image_h"], src["image_sha"],
                          src["image_prompt"], src["source_url"]))
                    asset_id = cur.fetchone()[0]

                    cur.execute("""
                        INSERT INTO content.matching_pool_item
                          (exercise_id, side, text, asset_id, order_no, extra)
                        VALUES
                          (%s, 'R', NULL, %s, %s, jsonb_build_object('label', %s))
                        RETURNING id
                    """, (exercise_id, asset_id, i + 1, label))
                    right_item_ids[label] = cur.fetchone()[0]

                # 5.2 左列文本 matching_pool_item
                left_item_ids = {}
                for i, item in enumerate(generated_items):
                    item_number = str(i + 1)
                    cur.execute("""
                        INSERT INTO content.matching_pool_item
                          (exercise_id, side, text, asset_id, order_no, extra)
                        VALUES
                          (%s, 'L', %s, NULL, %s, jsonb_build_object('item_number', %s, 'keyword', %s))
                        RETURNING id
                    """, (exercise_id, item["reading_text"], item_number, item_number, item["keyword"]))
                    left_item_ids[item_number] = cur.fetchone()[0]

                # 5.3 建立正确配对
                for i, item in enumerate(generated_items):
                    item_number = str(i + 1)
                    correct_label = answers[item_number]
                    left_id = left_item_ids[item_number]
                    right_id = right_item_ids[correct_label]
                    cur.execute("""
                        INSERT INTO content.matching_pair(exercise_id, left_item_id, right_item_id)
                        VALUES (%s, %s, %s)
                    """, (exercise_id, left_id, right_id))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB error: {e}")

    return ReadingMatchResp(
        question_type="阅读·看图配对",
        hsk_level=body.hskLevel,
        shuffled_images=shuffled_images,
        reading_items=[{"item_number": i + 1, "text": item["reading_text"]} for i, item in enumerate(generated_items)],
        answers=answers,
        exercise_id=str(exercise_id)
    )



class ReadingDialogMatchReq(BaseModel):
    keyword: str
    hskLevel: int = Field(..., ge=1, le=6)
    numPairs: int = Field(5, ge=2, le=6)
    lang: str = "zh-CN"
    difficulty: int = Field(2, ge=1, le=5)

class ReadingDialogMatchResp(BaseModel):
    question_type: str
    hsk_level: int
    shuffled_questions: Dict[str, str]  # {"A": "问句", ...}
    shuffled_answers: Dict[str, str]    # {"B": "答句", ...}
    answers: Dict[str, str]             # {"A": "C", "B": "D", ...}
    exercise_id: str

@router.post("/api/generate/reading-dialog-matching", response_model=ReadingDialogMatchResp)
async def generate_reading_dialog_matching(body: ReadingDialogMatchReq):
    """
    生成【阅读·对话配对】并落库。
    学生阅读左右两列的文本，然后进行匹配。
    """
    hskExplain = HSK_LEVEL_DESCRIPTIONS.get(body.hskLevel, "无特定描述")

    # 1) LLM 生成多组“问-答”对话
    prompt_dialog = f"""
请围绕关键词“{body.keyword}”设计{body.numPairs}组一问一答的中文日常对话，适用于HSK{body.hskLevel}级别。
要求：
1. 每组为一问一答，问句与答句语言自然简洁，角色不超过2人；
2. 语言符合HSK{body.hskLevel}级词汇与语法；
3. 每组问答应相互独立，不构成连续对话；
4. 返回 JSON 格式：
{{
  "pairs": [
    {{ "question": "问句1", "answer": "回答1" }},
    {{ "question": "问句2", "answer": "回答2" }},
    ...
  ]
}}
5. 不要添加解释说明，仅返回 JSON 格式。
""".strip()
    raw = generate_from_llm(prompt_dialog).strip()
    try:
        pairs: List[Dict[str, str]] = json.loads(raw)["pairs"]
        if len(pairs) != body.numPairs:
            raise ValueError(f"LLM未返回指定数量的对话对，预期{body.numPairs}对，实际{len(pairs)}对。")
        for pair in pairs:
            if "question" not in pair or "answer" not in pair:
                raise ValueError("LLM返回的JSON格式不正确，缺少'question'或'answer'键。")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM返回解析失败或格式错误: {e}")

    # 2) 乱序左右列并生成答案映射
    labels = ["A", "B", "C", "D", "E", "F"][:body.numPairs]
    questions = [p["question"] for p in pairs]
    answers_texts = [p["answer"] for p in pairs]

    shuffled_questions = questions[:]
    shuffled_answers = answers_texts[:]
    random.shuffle(shuffled_questions)
    random.shuffle(shuffled_answers)

    questions_map = {labels[i]: shuffled_questions[i] for i in range(len(shuffled_questions))}
    answers_map = {labels[i]: shuffled_answers[i] for i in range(len(shuffled_answers))}

    correct_answers = {}
    for i, original_q in enumerate(questions):
        # 找到原始问句对应的乱序后标签
        q_label = next(k for k, v in questions_map.items() if v == original_q)
        # 找到原始问句对应的正确回答
        original_a = next(p["answer"] for p in pairs if p["question"] == original_q)
        # 找到正确回答对应的乱序后标签
        a_label = next(k for k, v in answers_map.items() if v == original_a)
        correct_answers[q_label] = a_label

    # 3) 事务落库
    exercise_id = None
    try:
        with _db() as conn:
            with conn.cursor() as cur:
                # 3.1 exercise 主表
                cur.execute("""
                    INSERT INTO content.exercise
                      (skill, format, title, stem_text, lang, hsk_level, difficulty, points)
                    VALUES
                      ('reading','dialog_match',
                       '阅读·对话配对',
                       '请将左侧的问句与右侧的回答配对。',
                       %s, %s, %s, 1.0)
                    RETURNING id
                """, (body.lang, body.hskLevel, body.difficulty))
                exercise_id = cur.fetchone()[0]

                # 3.2 左列（问句）: matching_pool_item
                left_item_map = {}
                for i, label in enumerate(labels):
                    q_text = questions_map[label]
                    cur.execute("""
                        INSERT INTO content.matching_pool_item
                          (exercise_id, side, text, asset_id, order_no, extra)
                        VALUES
                          (%s, 'L', %s, NULL, %s, jsonb_build_object('label', %s))
                        RETURNING id
                    """, (exercise_id, q_text, i + 1, label))
                    left_item_map[q_text] = cur.fetchone()[0]

                # 3.3 右列（答句）: matching_pool_item
                right_item_map = {}
                for i, label in enumerate(labels):
                    a_text = answers_map[label]
                    cur.execute("""
                        INSERT INTO content.matching_pool_item
                          (exercise_id, side, text, asset_id, order_no, extra)
                        VALUES
                          (%s, 'R', %s, NULL, %s, jsonb_build_object('label', %s))
                        RETURNING id
                    """, (exercise_id, a_text, i + 1, label))
                    right_item_map[a_text] = cur.fetchone()[0]

                # 3.4 建立正确配对
                for pair in pairs:
                    left_id = left_item_map[pair["question"]]
                    right_id = right_item_map[pair["answer"]]
                    cur.execute("""
                        INSERT INTO content.matching_pair(exercise_id, left_item_id, right_item_id)
                        VALUES (%s, %s, %s)
                    """, (exercise_id, left_id, right_id))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB error: {e}")

    # 4) 返回
    return ReadingDialogMatchResp(
        question_type="阅读·对话配对",
        hsk_level=body.hskLevel,
        shuffled_questions=questions_map,
        shuffled_answers=answers_map,
        answers=correct_answers,
        exercise_id=str(exercise_id),
    )



class SentenceJudgeReq(BaseModel):
    keyword: str
    hskLevel: int = Field(..., ge=1, le=6)
    lang: str = "zh-CN"
    difficulty: int = Field(2, ge=1, le=5)

class SentenceJudgeResp(BaseModel):
    question_type: str
    hsk_level: int
    generated_text: str
    question: str
    correct_answer: str
    exercise_id: str

@router.post("/api/generate/sentence-judgment", response_model=SentenceJudgeResp)
async def generate_sentence_judgment(body: SentenceJudgeReq):
    """
    生成【句子理解·判断题】并落库
    """
    hskExplain = HSK_LEVEL_DESCRIPTIONS.get(body.hskLevel, "无特定描述")

    # 1) LLM生成句子、问题和答案
    prompt = f"""
请根据以下要求生成一句话，并根据该句话设计语义理解判断题，并给出正确答案。
1. 请根据以下关键词：{body.keyword}生成连贯的文本。
2. 确保文本的语句通顺，内容积极向上，且符合HSK{body.hskLevel}级别（{hskExplain}）。
3. 文本长度为一两句话，包含20-30字。
4. 基于文本设计一个判断题，可以是符合文本意思（答案为True），也可以与文本意思相反（答案为False），但必须与文本有明显逻辑关联。
5. 返回严格JSON格式，不要多余文字或不可解析的字符：
{{
  "generated_text": "...",
  "question": "...",
  "answer": "True/False"
}}
""".strip()
    raw = generate_from_llm(prompt).strip()
    try:
        js = json.loads(raw)
        generated_text = str(js["generated_text"]).strip()
        question = str(js["question"]).strip()
        answer = str(js["answer"]).lower() in ("true", "正确")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM 返回解析失败: {e}")
    
    # 2) 事务入库
    exercise_id = None
    try:
        with _db() as conn:
            with conn.cursor() as cur:
                # exercise 主表
                cur.execute("""
                    INSERT INTO content.exercise
                      (skill, format, title, stem_text, lang, hsk_level, difficulty, points)
                    VALUES
                      ('reading','sentence_tf',
                       '句子理解·判断',
                       %s, %s, %s, %s, 1.0)
                    RETURNING id
                """, ("请阅读下面的句子，判断给出的陈述是否正确。", body.lang, body.hskLevel, body.difficulty))
                exercise_id = cur.fetchone()[0]

                # detail
                cur.execute("""
                    INSERT INTO content.exercise_tf_detail
                      (exercise_id, correct_is_true, explanation, transcript_text, core_keyword, meta)
                    VALUES
                      (%s, %s, %s, NULL, %s,
                        jsonb_build_object('statement', %s, 'generated_text', %s))
                """, (
                    exercise_id,
                    answer,
                    "判断题中的陈述与原句意思一致则为“正确”，不一致则为“错误”。",
                    body.keyword,
                    question,
                    generated_text
                ))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB error: {e}")

    # 3) 返回
    return SentenceJudgeResp(
        question_type="句子理解·判断",
        hsk_level=body.hskLevel,
        generated_text=generated_text,
        question=question,
        correct_answer="正确" if answer else "错误",
        exercise_id=str(exercise_id),
    )


class ReadingSentChoiceReq(BaseModel):
    keyword: str
    hskLevel: int = Field(..., ge=1, le=6)
    lang: str = "zh-CN"
    difficulty: int = Field(2, ge=1, le=5)

class ReadingSentChoiceResp(BaseModel):
    question_type: str
    hsk_level: int
    generated_text: str
    question: str
    options: Dict[str, str]
    correct_answer: str
    exercise_id: str

@router.post("/api/generate/reading-sentence-choice", response_model=ReadingSentChoiceResp)
async def generate_reading_sentence_choice(body: ReadingSentChoiceReq):
    """
    生成【阅读·句子理解（选择题）】并落库
    """
    hskExplain = HSK_LEVEL_DESCRIPTIONS.get(body.hskLevel, "无特定描述")

    # 1) LLM生成句子、问题和选项
    prompt = f"""
请根据以下要求生成一段连贯的文本，并根据文本内容设计语义理解选择题，并给出正确答案：
1. 请根据以下关键词：{body.keyword}生成连贯的文本。
2. 确保文本的语句通顺，内容积极向上，且符合HSK{body.hskLevel}级别（{hskExplain}）。
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
        js = json.loads(raw)
        generated_text = str(js["generated_text"]).strip()
        question = str(js["question"]).strip()
        options_list: List[str] = [str(o).strip() for o in js["options"]]
        answer_letter = str(js["answer"]).strip().upper()
        if len(options_list) != 3 or answer_letter not in ("A", "B", "C"):
            raise ValueError("options 必须3项且 answer ∈ {A,B,C}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM 返回解析失败: {e}")

    # 2) 事务入库
    exercise_id = None
    try:
        with _db() as conn:
            with conn.cursor() as cur:
                # exercise 主表
                cur.execute("""
                    INSERT INTO content.exercise
                      (skill, format, title, stem_text, lang, hsk_level, difficulty, points)
                    VALUES
                      ('reading','sentence_choice',
                       '句子理解·单选',
                       %s, %s, %s, %s, 1.0)
                    RETURNING id
                """, (question, body.lang, body.hskLevel, body.difficulty))
                exercise_id = cur.fetchone()[0]
                
                # options 和 answer_key
                option_ids: Dict[str, str] = {}
                labels = ["A", "B", "C"]
                for idx, (label, text) in enumerate(zip(labels, options_list), start=1):
                    cur.execute("""
                        INSERT INTO content.option(exercise_id, label, text, order_no)
                        VALUES (%s, %s, %s, %s)
                        RETURNING id
                    """, (exercise_id, label, text, idx))
                    option_ids[label] = cur.fetchone()[0]

                cur.execute("""
                    INSERT INTO content.answer_key(exercise_id, option_id, is_correct, score)
                    VALUES (%s, %s, TRUE, 1.0)
                """, (exercise_id, option_ids[answer_letter]))

                # detail（保存原始文本）
                cur.execute("""
                    INSERT INTO content.listening_detail
                      (exercise_id, transcript_text, show_transcript, meta)
                    VALUES (%s, %s, FALSE,
                            jsonb_build_object('question_text', %s, 'keyword', %s))
                """, (exercise_id, generated_text, question, body.keyword))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB error: {e}")

    # 3) 返回
    return ReadingSentChoiceResp(
        question_type="句子理解·单选",
        hsk_level=body.hskLevel,
        generated_text=generated_text,
        question=question,
        options={labels[0]: options_list[0], labels[1]: options_list[1], labels[2]: options_list[2]},
        correct_answer=answer_letter,
        exercise_id=str(exercise_id),
    )



class DialogOrderingReq(BaseModel):
    keyword: str
    hskLevel: int = Field(..., ge=1, le=6)
    numLines: int = Field(5, ge=3, le=8)
    lang: str = "zh-CN"
    difficulty: int = Field(2, ge=1, le=5)
    show_transcript: bool = False

class DialogOrderingResp(BaseModel):
    question_type: str
    hsk_level: int
    shuffled_dialogue: List[str] # ["文本A", "文本B", ...]
    answers: Dict[str, str]           # {"1": "B", "2": "A"}
    exercise_id: str

@router.post("/api/generate/dialog-ordering", response_model=DialogOrderingResp)
async def generate_dialog_ordering(body: DialogOrderingReq):
    """
    生成【对话排序】并落库 (无 order_no 版本)
    """
    hskExplain = HSK_LEVEL_DESCRIPTIONS.get(body.hskLevel, "无特定描述")

    # 1) LLM生成一段完整、连贯的对话
    prompt_dialog = f"""
请围绕关键词“{body.keyword}”设计一段自然、连贯的中文对话，适用于HSK{body.hskLevel}级别。
要求：
1. 包含{body.numLines}个对话回合。
2. 语言符合HSK{body.hskLevel}级词汇与语法。
3. 对话必须有明确的逻辑顺序，情节完整。
4. 返回严格 JSON 格式，其中每个对话回合为一个独立的字符串：
{{
  "lines": [
    "第一回合",
    "第二回合",
    ...
  ]
}}
5. 不要添加任何解释说明，仅返回 JSON 格式。
""".strip()
    raw = generate_from_llm(prompt_dialog).strip()
    try:
        lines: List[str] = json.loads(raw)["lines"]
        if len(lines) != body.numLines:
            raise ValueError(f"LLM未返回指定数量的对话回合，预期{body.numLines}个，实际{len(lines)}个。")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM返回解析失败或格式错误: {e}")

    # 2) 乱序对话片段并生成答案映射
    shuffled_lines = lines[:]
    random.shuffle(shuffled_lines)
    
    # 因为没有 order_no，答案的映射关系改为 正确顺序 -> 乱序后的文本
    # 比如 "1" -> "你好吗？"
    answers = {str(i+1): lines[i] for i in range(len(lines))}

    # 3) 事务入库
    exercise_id = None
    try:
        with _db() as conn:
            with conn.cursor() as cur:
                # 3.1 exercise 主表
                cur.execute("""
                    INSERT INTO content.exercise
                      (skill, format, title, stem_text, lang, hsk_level, difficulty, points)
                    VALUES
                      ('reading','dialog_ordering',
                       '对话排序',
                       '请将下列对话片段重新排序，组成一段完整的对话。',
                       %s, %s, %s, 1.0)
                    RETURNING id
                """, (body.lang, body.hskLevel, body.difficulty))
                exercise_id = cur.fetchone()[0]

                # 3.2 ordering_item
                for i, original_line in enumerate(lines, start=1):
                    # 只保存 correct_position，不保存 order_no
                    cur.execute("""
                        INSERT INTO content.ordering_item
                          (exercise_id, text, correct_position)
                        VALUES
                          (%s, %s, %s)
                    """, (exercise_id, original_line, i))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB error: {e}")

    # 4) 返回
    return DialogOrderingResp(
        question_type="对话排序",
        hsk_level=body.hskLevel,
        shuffled_dialogue=shuffled_lines,
        answers=answers,
        exercise_id=str(exercise_id),
    )

class ReadingPassageReq(BaseModel):
    hskLevel: int = Field(..., ge=1, le=6)
    topic: str
    textLength: int = Field(300, ge=80, le=1200)   # 文章字数
    numQuestions: int = Field(2, ge=1, le=10)      # 生成题目数量
    lang: str = "zh-CN"
    difficulty: int = Field(3, ge=1, le=5)

class RPChoiceOption(BaseModel):
    id: str
    content: str

class RPQuestionItem(BaseModel):
    stem: str
    options: List[RPChoiceOption]
    correctIndex: int

class ReadingPassageResp(BaseModel):
    context_exercise_id: str
    passage_title: str
    passage_text: str
    questions: List[RPQuestionItem]
    question_exercise_ids: List[str]

@router.post("/api/generate/reading-passage-choice-bundle", response_model=ReadingPassageResp)
async def generate_reading_passage_choice_bundle(body: ReadingPassageReq):
    """
    生成一段文章 + N 道单选题，并全部落库。
    载体题(skill='reading', format='paragraph_choice')承载文章文本；
    每个子题都是 paragraph_choice。
    """

    # 1) 生成文章
    hskExplain = HSK_LEVEL_DESCRIPTIONS.get(body.hskLevel, "无特定描述")
    prompt_passage = f"""
请根据以下要求生成一段中文文章：
- **主题**：{body.topic}
- **HSK 等级**：HSK{body.hskLevel}（{hskExplain}）
- **字数**：约 {body.textLength} 字（可±10%）
- **风格**：句子通顺、逻辑自然、积极向上，可分为多个自然段；仅返回正文，不要任何解释或标题。
- **特殊要求**: 在文章中**随机**选择一个词汇，用斜杠 `/` 包裹起来，例如 `/稀有/`。
- **输出格式**：返回 JSON 格式，例如:
{{
  "generated_text": "文章正文"
}}
""".strip()
    raw_passage = generate_from_llm(prompt_passage).strip()
    try:
        passage_text = json.loads(raw_passage)["generated_text"].strip().replace("/", "")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"文章生成失败或格式错误: {e}")
    
    # 2) 生成 N 道单选题（避免重复）
    questions: List[RPQuestionItem] = []
    for i in range(body.numQuestions):
        existed = "\n".join([f'问题{idx+1}: {q.stem}' for idx, q in enumerate(questions)])
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
        raw = generate_from_llm(q_prompt).strip()
        try:
            js = json.loads(raw)
            opts = js.get("options", [])
            if not isinstance(opts, list) or len(opts) != 4:
                raise ValueError("必须返回4个选项")
            item = RPQuestionItem(
                stem=str(js["question"]).strip(),
                options=[RPChoiceOption(id=lab, content=str(opts[i]["content"]).strip())
                         for i, lab in enumerate(["A","B","C","D"])],
                correctIndex=int(js["correctIndex"])
            )
            if item.correctIndex not in (0,1,2,3):
                raise ValueError("correctIndex 需在 0..3")
            questions.append(item)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"生成问题失败: {e}")

    # 3) 事务落库
    try:
        with _db() as conn:
            with conn.cursor() as cur:
                # 3.1 载体题（承载文章）
                cur.execute("""
                    INSERT INTO content.exercise
                      (skill, format, title, stem_text, lang, hsk_level, difficulty, points)
                    VALUES ('reading','paragraph_choice',
                            '阅读理解',
                            '请阅读下面的文章，然后回答后面的选择题。',
                            %s, %s, %s, 1.0)
                    RETURNING id
                """, (body.lang, body.hskLevel, body.difficulty))
                context_exercise_id = cur.fetchone()[0]

                # 3.2 passage_detail（保存文章）
                cur.execute("""
                    INSERT INTO content.passage_detail
                      (exercise_id, passage_title, passage_text, passage_lang, meta)
                    VALUES (%s, %s, %s, %s, jsonb_build_object('topic', %s, 'length_hint', %s))
                """, (context_exercise_id, body.topic, passage_text, body.lang, body.topic, body.textLength))

                # 3.3 建 N 条单选题
                question_exercise_ids = []
                for idx, q in enumerate(questions, start=1):
                    cur.execute("""
                        INSERT INTO content.exercise
                          (skill, format, title, stem_text, lang, hsk_level, difficulty, points, extra)
                        VALUES ('reading','paragraph_choice',
                                '段落理解·单选', %s,
                                %s, %s, %s, 1.0,
                                jsonb_build_object('context_exercise_id', %s, 'order_in_group', %s))
                        RETURNING id
                    """, (q.stem, body.lang, body.hskLevel, body.difficulty, context_exercise_id, idx))
                    q_exercise_id = cur.fetchone()[0]
                    question_exercise_ids.append(str(q_exercise_id))

                    # 选项
                    labels = ["A","B","C","D"]
                    opt_ids = []
                    for order_no, (lab, opt) in enumerate(zip(labels, q.options), start=1):
                        cur.execute("""
                            INSERT INTO content.option(exercise_id, label, text, order_no)
                            VALUES (%s, %s, %s, %s)
                            RETURNING id
                        """, (q_exercise_id, lab, opt.content, order_no))
                        opt_ids.append(cur.fetchone()[0])

                    # 正确答案
                    correct_opt_id = opt_ids[q.correctIndex]
                    cur.execute("""
                        INSERT INTO content.answer_key(exercise_id, option_id, is_correct, score)
                        VALUES (%s, %s, TRUE, 1.0)
                    """, (q_exercise_id, correct_opt_id))

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB error: {e}")

    return ReadingPassageResp(
        context_exercise_id=str(context_exercise_id),
        passage_title=body.topic,
        passage_text=passage_text,
        questions=questions,
        question_exercise_ids=question_exercise_ids
    )

class PinyinClozeReq(BaseModel):
    sentence: str
    hskLevel: int = Field(..., ge=1, le=6)
    lang: str = "zh-CN"
    difficulty: int = Field(2, ge=1, le=5)

class PinyinClozeResp(BaseModel):
    question_type: str
    hsk_level: int
    stem_text: str
    blank_answer: str
    exercise_id: str

####修改
@router.post("/api/generate/pinyin-cloze", response_model=PinyinClozeResp)
async def generate_pinyin_cloze(body: PinyinClozeReq):
    """
    生成【拼音填空题】并落库 (下划线用拼音代替)
    """
    # 1) LLM分析句子，并返回填空位置和答案
    prompt = f"""
你是一个顶尖的中文教学内容设计师，请为【拼音填空】题型创作一道题目。
- **任务**: 从用户提供的中文句子中，选择一个或几个难度适中的词语作为填空点。
- **句子**: "{body.sentence}"
- **要求**:
  1. 识别并选择一个或多个词语作为填空答案。
  2. 提供一个完整的题干，其中填空词语用其拼音代替，并在前后添加**双下划线**作为标记。
  3. 提供每个填空点对应的标准答案（汉字）和拼音。
  4. 难度需符合HSK{body.hskLevel}级。
- **输出格式**: 严格遵循 JSON 格式，不要多余文字：
{{
  "stem_text": "例如：我每天都去__xué xiào__打球。",
  "blanks": [
    {{
      "word": "学校",
      "pinyin": "xué xiào"
    }}
  ]
}}
""".strip()
    raw = generate_from_llm(prompt).strip()
    try:
        js = json.loads(raw)
        stem_text = str(js["stem_text"]).strip()
        blanks: List[Dict[str, str]] = js["blanks"]
        if not blanks:
            raise ValueError("LLM未返回填空点。")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM 返回解析失败或格式错误: {e}")
    
    # 将多个填空答案组合成一个字符串，便于返回和保存
    blank_answer = " ".join([b["word"] for b in blanks])
    
    # 2) 事务入库
    exercise_id = None
    try:
        with _db() as conn:
            with conn.cursor() as cur:
                # 2.1 exercise 主表
                cur.execute("""
                    INSERT INTO content.exercise
                      (skill, format, title, stem_text, lang, hsk_level, difficulty, points)
                    VALUES
                      ('writing','pinyin_cloze',
                       '拼音填空',
                       '根据句子中的拼音提示，写出正确的汉字。',
                       %s, %s, %s, 1.0)
                    RETURNING id
                """, (body.lang, body.hskLevel, body.difficulty))
                exercise_id = cur.fetchone()[0]

                # 2.2 cloze_detail
                # 这里的cloze_text直接保存带有拼音的题干
                cur.execute("""
                    INSERT INTO content.cloze_detail
                      (exercise_id, cloze_text, blank_token, mode)
                    VALUES
                      (%s, %s, '__', 'pinyin')
                """, (exercise_id, stem_text))
                
                # 2.3 cloze_blank
                for idx, blank in enumerate(blanks):
                    cur.execute("""
                        INSERT INTO content.cloze_blank
                          (exercise_id, blank_index, answer, alt_answers, match_mode, score)
                        VALUES
                          (%s, %s, %s, %s, 'exact', 1.0)
                    """, (exercise_id, idx + 1, blank["word"], None))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB error: {e}")

    # 3) 返回
    return PinyinClozeResp(
        question_type="拼音填空",
        hsk_level=body.hskLevel,
        stem_text=stem_text,
        blank_answer=blank_answer,
        exercise_id=str(exercise_id),
    )




class CompositionReq(BaseModel):
    hskLevel: int = Field(..., ge=1, le=6)
    lang: str = "zh-CN"
    difficulty: int = Field(4, ge=1, le=5)

class CompositionResp(BaseModel):
    question_type: str
    hsk_level: int
    title: str
    prompt_text: str
    min_words: int
    max_words: int
    exercise_id: str

@router.post("/api/generate/composition-topic", response_model=CompositionResp)
async def generate_composition_topic(body: CompositionReq):
    """
    生成【写作/作文题目】并落库。
    """
    hskExplain = HSK_LEVEL_DESCRIPTIONS.get(body.hskLevel, "无特定描述")

    # 1) LLM生成作文题目、要求和字数
    prompt = f"""
请根据HSK{body.hskLevel}级别（{hskExplain}）生成一个中文作文题目。
要求：
1. 题目描述要清晰明确，给出具体的写作要求和字数要求（例如：不少于100字，不超过150字）。
2. 题目应该符合该级别学生的语言水平。
3. 返回严格 JSON 格式，不要多余文字：
{{
  "title": "作文题目",
  "prompt_text": "具体写作要求",
  "min_words": 100,
  "max_words": 150
}}
""".strip()
    raw = generate_from_llm(prompt).strip()
    try:
        js = json.loads(raw)
        title = str(js["title"]).strip()
        prompt_text = str(js["prompt_text"]).strip()
        min_words = int(js["min_words"])
        max_words = int(js["max_words"])
        if not title or not prompt_text:
            raise ValueError("LLM返回的题目或要求为空。")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"LLM 返回解析失败或格式错误: {e}")
    
    # 2) 事务入库
    exercise_id = None
    try:
        with _db() as conn:
            with conn.cursor() as cur:
                # 2.1 exercise 主表
                cur.execute("""
                    INSERT INTO content.exercise
                      (skill, format, title, stem_text, lang, hsk_level, difficulty, points)
                    VALUES
                      ('writing','keyword_essay',
                       %s, %s,
                       %s, %s, %s, 1.0)
                    RETURNING id
                """, (title, prompt_text, body.lang, body.hskLevel, body.difficulty))
                exercise_id = cur.fetchone()[0]

                # 2.2 writing_detail
                # 因为没有关键词和评分标准，只存储核心信息
                cur.execute("""
                    INSERT INTO content.writing_detail
                      (exercise_id, prompt_text, min_words, max_words)
                    VALUES
                      (%s, %s, %s, %s)
                """, (exercise_id, prompt_text, min_words, max_words))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB error: {e}")

    # 3) 返回
    return CompositionResp(
        question_type="写作",
        hsk_level=body.hskLevel,
        title=title,
        prompt_text=prompt_text,
        min_words=min_words,
        max_words=max_words,
        exercise_id=str(exercise_id),
    )




class SentenceCreationReq(BaseModel):
    keyword: str
    imagePrompt: str
    hskLevel: int = Field(..., ge=1, le=6)
    lang: str = "zh-CN"
    difficulty: int = Field(2, ge=1, le=5)

class SentenceCreationResp(BaseModel):
    question_type: str
    hsk_level: int
    image_url: str
    given_word: str
    sample_answer: str
    exercise_id: str

@router.post("/api/generate/picture-sentence-creation", response_model=SentenceCreationResp)
async def generate_picture_sentence_creation(body: SentenceCreationReq):
    """
    生成【看图·用词造句】题目并落库
    """
    hskExplain = HSK_LEVEL_DESCRIPTIONS.get(body.hskLevel, "无特定描述")

    # 1) LLM 生成例句
    prompt = f"""
作为一名顶尖的中文教学（CSL）专家与语言润色师，你的任务是根据一个具体的场景描述和给定的核心词语，创作一个高质量的例句。

**1. 核心任务与目标**
- **核心任务**: 根据以下“场景描述”和“核心词语”创作一个中文句子。
- **核心目标**:
  - **包含核心词语**: 句子必须包含`{body.keyword}`。
  - **符合场景**: 句子必须能准确描述`{body.imagePrompt}`这个场景。
  - **匹配语言水平**: 句子的词汇和语法结构必须严格符合HSK{body.hskLevel}等级。

**2. 输入信息**
- **场景描述**: `{body.imagePrompt}`
- **核心词语**: `{body.keyword}`
- **目标语言水平**: HSK {body.hskLevel}（{hskExplain}）

**3. 重要原则**
- **自然地道**: 语言风格必须自然，符合现代汉语的日常用法。
- **严格遵从等级**: 避免使用超纲的词汇和复杂的语法结构。

**4. 输出格式**
- 请直接输出最终创作好的句子。
- 不要包含任何额外的标题、解释、标签或对输入信息的引用。
""".strip()
    sample_answer_sentence = generate_from_llm(prompt).strip()
    if not sample_answer_sentence:
        raise HTTPException(status_code=500, detail="AI生成例句失败")

    # 2) 文生图
    image_prompt = f'请根据以下描述生成一张清晰、写实的图片，画面中不要出现任何文字： "{body.imagePrompt}"'
    init = generate_image(image_prompt, "文字, 丑陋, 模糊")
    task_id = init.get("output", {}).get("task_id")
    if not task_id:
        raise HTTPException(status_code=500, detail="文生图任务未返回 task_id")

    image_url = await _poll_image_task(task_id)
    if not image_url:
        raise HTTPException(status_code=500, detail="文生图任务失败或超时")

    # 下载并保存图片
    oss_image_url = url_without_course(image_url) or image_url
    img_resp = requests.get(oss_image_url, timeout=60)
    if not img_resp.ok:
        raise HTTPException(status_code=500, detail="下载图片失败")
    img_bytes = img_resp.content
    img_mime = img_resp.headers.get("Content-Type", "image/jpeg").split(";")[0]
    image_public_url, image_rel, image_size, w, h, img_sha = save_image_bytes(img_bytes, img_mime)

    # 3) 事务入库
    exercise_id = None
    try:
        with _db() as conn:
            with conn.cursor() as cur:
                # 3.1 asset: image
                cur.execute("""
                    INSERT INTO content.asset
                      (media_kind, url, file_path, mime_type, size_bytes, width, height, checksum_sha256, meta)
                    VALUES
                      ('image', %s, %s, %s, %s, %s, %s, %s,
                        jsonb_build_object('prompt', %s, 'source_url', %s))
                    RETURNING id
                """, (image_public_url, image_rel, img_mime, image_size, w, h, img_sha, image_prompt, oss_image_url))
                image_asset_id = cur.fetchone()[0]

                # 3.2 exercise
                cur.execute("""
                    INSERT INTO content.exercise
                    (skill, format, title, stem_text, lang, hsk_level, difficulty, points)
                 VALUES
                    ('writing', 'picture_keyword_essay',
                    '看图用词造句',
                    '请看图，并使用给出的词语造一个句子。',
                    %s, %s, %s, 1.0)
                    RETURNING id
                """, (body.lang, body.hskLevel, body.difficulty))
                exercise_id = cur.fetchone()[0]

                # 3.3 writing_detail
                # 提示文本保存关键词和例句
                cur.execute("""
                    INSERT INTO content.writing_detail
                      (exercise_id, prompt_text, required_keys)
                    VALUES
                      (%s, %s, %s)
                """, (exercise_id, sample_answer_sentence, [body.keyword]))

                # 3.4 关联题图
                cur.execute("""
                    INSERT INTO content.exercise_asset
                      (exercise_id, asset_id, role, position)
                    VALUES (%s, %s, 'stem_image', 1)
                """, (exercise_id, image_asset_id))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB error: {e}")

    # 4) 返回
    return SentenceCreationResp(
        question_type="书写：看图用词造句",
        hsk_level=body.hskLevel,
        image_url=image_public_url,
        given_word=body.keyword,
        sample_answer=sample_answer_sentence,
        exercise_id=str(exercise_id),
    )





