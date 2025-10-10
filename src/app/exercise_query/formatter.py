# file: question/formatter.py

from typing import List, Optional, Any
from . import models
from . import schemas
import os


def build_public_url(file_url: Optional[str], base_url: Optional[str] = None) -> str:
    """
    把数据库里保存的相对路径（如 'images/xx.png' 或 '/media/images/xx.png'）
    统一转换为可公网访问的绝对 URL。
    优先使用环境变量 MEDIA_PUBLIC_BASE；若它是路径（如 '/media'），再用 base_url 兜底。
    """
    if not file_url:
        return ""

    low = file_url.lower()
    if low.startswith("http://") or low.startswith("https://"):
        return file_url  # 已是绝对 URL

    # 归一：去掉开头的斜杠与 'media/' 前缀
    rel = file_url.lstrip("/")
    if rel.startswith("media/"):
        rel = rel.split("media/", 1)[1]

    mpb = os.getenv("MEDIA_PUBLIC_BASE", "/media").rstrip("/")
    if mpb.startswith("http://") or mpb.startswith("https://"):
        return f"{mpb}/{rel}"

    # mpb 只是路径，需要 base_url 来拼成绝对地址
    if base_url:
        return f"{base_url.rstrip('/')}{mpb}/{rel}"

    # 兜底（同域同端口部署也能工作）
    return f"{mpb}/{rel}"


def _build_media_map(exercise: models.Exercise, base_url: Optional[str]) -> dict:
    """
    从 exercise.media_links 构建 {usage_role: 绝对URL} 的字典。
    usage_role 例如: 'prompt_audio', 'stem_image', 'option_image_A' 等。
    """
    if not exercise.media_links:
        return {}
    return {
        link.usage_role: build_public_url(link.media_asset.file_url, base_url)
        for link in exercise.media_links
        if link.media_asset
    }


def _abs_item_url(item: Any, key: str, base_url: Optional[str]) -> Any:
    """
    把字典 item 中 key 指向的值（通常是 'audioUrl' / 'imageUrl'）绝对化。
    若 item 非 dict 或不存在 key，则原样返回。
    """
    if isinstance(item, dict):
        val = item.get(key)
        if isinstance(val, str):
            item = {**item, key: build_public_url(val, base_url)}
    return item


def format_exercises_for_api(
    exercises: List[models.Exercise],
    base_url: Optional[str] = None
) -> List[schemas.AnyExercise]:
    """将 ORM 模型对象列表，格式化为 Pydantic 响应模型列表（所有媒体字段均为绝对 URL）"""
    formatted_list: List[schemas.AnyExercise] = []

    for exercise in exercises:
        ex_type = exercise.type.name if exercise.type else "UNKNOWN"
        metadata = exercise.meta or {}
        media_map = _build_media_map(exercise, base_url)

        if ex_type == "LISTEN_IMAGE_TRUE_FALSE":
            content = schemas.ListenImageTrueFalseContent(
                prompt=exercise.prompt or "",
                audioUrl=media_map.get("prompt_audio"),
                listeningText=metadata.get("listening_text", ""),
                imageUrl=media_map.get("stem_image"),
            )
            formatted_list.append(
                schemas.ListenImageTrueFalseExercise(
                    exerciseId=str(exercise.id),
                    exerciseType=ex_type,
                    content=content,
                    correctAnswer=metadata.get("correct_answer", False),
                )
            )

        elif ex_type == "READ_IMAGE_TRUE_FALSE":
            content = schemas.ReadImageTrueFalseContent(
                prompt=exercise.prompt or "",
                statement=metadata.get("word", ""),
                imageUrl=media_map.get("stem_image"),
            )
            formatted_list.append(
                schemas.ReadImageTrueFalseExercise(
                    exerciseId=str(exercise.id),
                    exerciseType=ex_type,
                    content=content,
                    correctAnswer=metadata.get("correct_answer", False),
                )
            )

        elif ex_type == "LISTEN_SENTENCE_TF":
            content = schemas.ListenSentenceTfContent(
                prompt=exercise.prompt or "",
                audioUrl=media_map.get("prompt_audio"),
                listeningText=metadata.get("listening_text", ""),
                statement=metadata.get("statement", ""),
            )
            formatted_list.append(
                schemas.ListenSentenceTfExercise(
                    exerciseId=str(exercise.id),
                    exerciseType=ex_type,
                    content=content,
                    correctAnswer=metadata.get("correct_answer", False),
                )
            )

        elif ex_type == "READ_SENTENCE_TF":
            content = schemas.ReadSentenceTfContent(
                prompt=exercise.prompt or "",
                passage=metadata.get("passage", ""),
                statement=metadata.get("statement", ""),
            )
            formatted_list.append(
                schemas.ReadSentenceTfExercise(
                    exerciseId=str(exercise.id),
                    exerciseType=ex_type,
                    content=content,
                    correctAnswer=metadata.get("correct_answer", False),
                )
            )

        elif ex_type == "LISTEN_IMAGE_MC":
            options = [
                schemas.McOptionImage(
                    label=opt.get("label"),
                    imageUrl=media_map.get(f'option_image_{opt.get("label")}'),
                )
                for opt in metadata.get("options", [])
            ]
            content = schemas.ListenImageMcContent(
                prompt=exercise.prompt or "",
                audioUrl=media_map.get("prompt_audio"),
                listeningText=metadata.get("listening_text", ""),
                options=options,
            )
            formatted_list.append(
                schemas.ListenImageMcExercise(
                    exerciseId=str(exercise.id),
                    exerciseType=ex_type,
                    content=content,
                    correctAnswer=metadata.get("correct_answer", ""),
                )
            )

        elif ex_type in [
            "LISTEN_SENTENCE_QA",
            "READ_SENTENCE_COMPREHENSION_CHOICE",
            "READ_WORD_GAP_FILL",
        ]:
            options = [schemas.McOptionText(**opt) for opt in metadata.get("options", [])]
            if ex_type == "LISTEN_SENTENCE_QA":
                content = schemas.ListenSentenceQaContent(
                    prompt=exercise.prompt or "",
                    audioUrl=media_map.get("prompt_audio"),
                    listeningText=metadata.get("listening_text", ""),
                    question=metadata.get("question", ""),
                    options=options,
                )
                formatted_list.append(
                    schemas.ListenSentenceQaExercise(
                        exerciseId=str(exercise.id),
                        exerciseType=ex_type,
                        content=content,
                        correctAnswer=metadata.get("correct_label", ""),
                    )
                )
            elif ex_type == "READ_SENTENCE_COMPREHENSION_CHOICE":
                content = schemas.ReadSentenceComprehensionChoiceContent(
                    prompt=exercise.prompt or "",
                    passage=metadata.get("passage", ""),
                    question=metadata.get("question", ""),
                    options=options,
                )
                formatted_list.append(
                    schemas.ReadSentenceComprehensionChoiceExercise(
                        exerciseId=str(exercise.id),
                        exerciseType=ex_type,
                        content=content,
                        correctAnswer=metadata.get("correct_label", ""),
                    )
                )
            elif ex_type == "READ_WORD_GAP_FILL":
                content = schemas.ReadWordGapFillContent(
                    prompt=exercise.prompt or "",
                    question=metadata.get("sentence_with_blank", ""),
                    options=options,
                )
                formatted_list.append(
                    schemas.ReadWordGapFillExercise(
                        exerciseId=str(exercise.id),
                        exerciseType=ex_type,
                        content=content,
                        correctAnswer=metadata.get("correct_label", ""),
                    )
                )

        elif ex_type in ["LISTEN_IMAGE_MATCH", "READ_IMAGE_MATCH", "READ_DIALOGUE_MATCH"]:
            # 注意：service 层可能已把 URL 处理为绝对地址；这里再兜底绝对化一次，安全无副作用。
            if ex_type == "LISTEN_IMAGE_MATCH":
                audios = metadata.get("audios", [])
                images = metadata.get("images", [])
                # 逐项绝对化
                audios = [_abs_item_url(item, "audioUrl", base_url) for item in audios]
                images = [_abs_item_url(item, "imageUrl", base_url) for item in images]

                left = [schemas.MatchItemAudio(**item) for item in audios]
                right = [schemas.MatchItemImage(**item) for item in images]

                content = schemas.ListenImageMatchContent(
                    prompt=exercise.prompt or "", leftItems=left, rightItems=right
                )
                formatted_list.append(
                    schemas.ListenImageMatchExercise(
                        exerciseId=str(exercise.id),
                        exerciseType=ex_type,
                        content=content,
                        correctAnswer=metadata.get("answer_map", {}),
                    )
                )

            elif ex_type == "READ_IMAGE_MATCH":
                texts = metadata.get("texts", [])
                images = metadata.get("images", [])
                images = [_abs_item_url(item, "imageUrl", base_url) for item in images]

                left = [schemas.MatchItemText(**item) for item in texts]
                right = [schemas.MatchItemImage(**item) for item in images]

                content = schemas.ReadImageMatchContent(
                    prompt=exercise.prompt or "", leftItems=left, rightItems=right
                )
                formatted_list.append(
                    schemas.ReadImageMatchExercise(
                        exerciseId=str(exercise.id),
                        exerciseType=ex_type,
                        content=content,
                        correctAnswer=metadata.get("answer_map", {}),
                    )
                )

            elif ex_type == "READ_DIALOGUE_MATCH":
                questions = metadata.get("shuffled_questions", [])
                answers = metadata.get("shuffled_answers", [])

                left = [schemas.MatchItemText(**item) for item in questions]
                right = [schemas.MatchItemText(**item) for item in answers]

                content = schemas.ReadDialogueMatchContent(
                    prompt=exercise.prompt or "", leftItems=left, rightItems=right
                )
                formatted_list.append(
                    schemas.ReadDialogueMatchExercise(
                        exerciseId=str(exercise.id),
                        exerciseType=ex_type,
                        content=content,
                        correctAnswer=metadata.get("answers", {}),
                    )
                )

        elif ex_type == "READ_WORD_ORDER":
            meta = metadata or {}
            label_map = meta.get("pieces_shuffled_label_map", None)
            shuffled_list = meta.get("pieces_shuffled", None)
            answer_ids = meta.get("answer_ids", None)
            answer_order = meta.get("answer_order", None)

            items = []
            correct_answer_numeric: List[str] = []

            if label_map:
                labels = sorted(label_map.keys())
                label_to_numeric = {lab: str(i + 1) for i, lab in enumerate(labels)}
                id_to_numeric = {}

                for i, lab in enumerate(labels, start=1):
                    piece = label_map.get(lab, {}) or {}
                    pid = piece.get("id") or ""
                    txt = piece.get("text", "")
                    id_to_numeric[pid] = str(i)
                    items.append(
                        schemas.WordOrderItem(
                            label=str(i),
                            **{"word": txt}
                        )
                    )
                if answer_ids:
                    correct_answer_numeric = [id_to_numeric.get(pid, "") for pid in answer_ids]
                elif answer_order:
                    correct_answer_numeric = [label_to_numeric.get(lab, "") for lab in answer_order]

                correct_answer_numeric = [x for x in correct_answer_numeric if x]

            elif shuffled_list:
                id_to_numeric = {}
                for i, piece in enumerate(shuffled_list, start=1):
                    pid = piece.get("id") or ""
                    txt = piece.get("text", "")
                    id_to_numeric[pid] = str(i)
                    items.append(
                        schemas.WordOrderItem(
                            label=str(i),
                            **{"word": txt}
                        )
                    )
                if answer_ids:
                    correct_answer_numeric = [id_to_numeric.get(pid, "") for pid in answer_ids]
                    correct_answer_numeric = [x for x in correct_answer_numeric if x]
                elif answer_order:
                    labels = [chr(ord("A") + i) for i in range(len(shuffled_list))]
                    label_to_numeric = {lab: str(i + 1) for i, lab in enumerate(labels)}
                    correct_answer_numeric = [label_to_numeric.get(lab, "") for lab in answer_order]
                    correct_answer_numeric = [x for x in correct_answer_numeric if x]

            prompt_text = (
                exercise.prompt
                or meta.get("sentence")
                or "请将下列词语按正确顺序排列成句。"
            )

            content = schemas.ReadWordOrderContent(
                prompt=prompt_text,
                **{"words": items}
            )
            formatted_list.append(
                schemas.ReadWordOrderExercise(
                    exerciseId=str(exercise.id),
                    exerciseType=ex_type,
                    content=content,
                    correctAnswer=correct_answer_numeric,
                )
            )

    return formatted_list
