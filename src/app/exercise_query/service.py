import math
import random
import uuid
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from . import schemas, crud, models
from .formatter import format_exercises_for_api, build_public_url   # ← 新增 build_public_url
from app.utils.avg_time import AVERAGE_DURATIONS_PER_TYPE

MAX_QUESTIONS_LIMIT = 50


def _calculate_average_duration(requested_types: List[str]) -> float:
    """计算请求题型的平均耗时"""
    if not requested_types:
        return AVERAGE_DURATIONS_PER_TYPE.get("DEFAULT", 15)
    total = sum(
        AVERAGE_DURATIONS_PER_TYPE.get(t, AVERAGE_DURATIONS_PER_TYPE["DEFAULT"])
        for t in requested_types
    )
    return total / len(requested_types)


def _reconstruct_matching_exercises(
    db: Session,
    exercises: List[models.Exercise],
    base_url: Optional[str] = None,   # ← 新增：把 base_url 透传进来用于拼绝对 URL
) -> List[models.Exercise]:
    """
    遍历题目列表，识别配对题的子题，重组成父题结构以供 formatter 使用。
    这是解决所有配对题查询问题的核心。
    这里也一并把所有媒体 URL（图片/音频）转换为“可公网访问的绝对 URL”。
    """
    reconstructed_list: List[models.Exercise] = []
    processed_parent_ids = set()
    MATCHING_TYPES = {"LISTEN_IMAGE_MATCH", "READ_IMAGE_MATCH", "READ_DIALOGUE_MATCH"}

    for exercise in exercises:
        ex_type_name = exercise.type.name if exercise.type else ""

        # 处理三类配对题（存在 parent_exercise_id 的子题）
        if ex_type_name in MATCHING_TYPES and exercise.parent_exercise_id:
            parent_id = exercise.parent_exercise_id

            if parent_id in processed_parent_ids:
                continue

            parent_exercise = crud.get_parent_exercise_with_all_children(db, parent_id)
            if not parent_exercise or not parent_exercise.children:
                continue

            # 关键修正(1): 必须使用 display_order 对子题排序，以确保原始配对关系正确
            sorted_children = sorted(parent_exercise.children, key=lambda x: x.display_order)

            parent_meta = parent_exercise.meta or {}
            seed = parent_meta.get("seed")
            rnd = random.Random(seed) if seed is not None else random

            reconstructed_meta = {}

            # A) 听图配对 / 读图配对
            if ex_type_name == "LISTEN_IMAGE_MATCH" or ex_type_name == "READ_IMAGE_MATCH":
                left_items, right_items = [], []
                for sub_ex in sorted_children:
                    sub_meta = sub_ex.meta or {}
                    # 使用 usage_role 建立媒体映射
                    media_map = {
                        link.usage_role: link.media_asset
                        for link in sub_ex.media_links
                        if link.media_asset
                    }

                    # 左列：听力音频 或 文本
                    if ex_type_name == "LISTEN_IMAGE_MATCH" and "prompt_audio" in media_map:
                        # 用 build_public_url 拼绝对 URL（不再硬编码 "/media/..."）
                        audio_url = build_public_url(
                            media_map["prompt_audio"].file_url, base_url
                        )
                        left_items.append(
                            {
                                "audioUrl": audio_url,
                                "listeningText": sub_meta.get("listening_text", ""),
                            }
                        )
                    elif ex_type_name == "READ_IMAGE_MATCH":
                        left_items.append(
                            {
                                "text": sub_meta.get("word", ""),
                                "pinyin": sub_meta.get("pinyin", ""),
                            }
                        )

                    # 右列：正确图片
                    if "correct_image" in media_map:
                        image_url = build_public_url(
                            media_map["correct_image"].file_url, base_url
                        )
                        right_items.append({"imageUrl": image_url})

                # 结构合法性检查
                if len(left_items) != len(right_items) or not left_items:
                    continue

                n = len(left_items)
                labels = [chr(ord("A") + i) for i in range(n)]
                left_indices, right_indices = list(range(n)), list(range(n))
                rnd.shuffle(left_indices)
                rnd.shuffle(right_indices)

                final_left = [
                    {"label": labels[i], **left_items[left_indices[i]]} for i in range(n)
                ]
                final_right = [
                    {"label": labels[i], **right_items[right_indices[i]]} for i in range(n)
                ]
                answer_map = {
                    labels[left_indices.index(i)]: labels[right_indices.index(i)]
                    for i in range(n)
                }

                if ex_type_name == "LISTEN_IMAGE_MATCH":
                    reconstructed_meta = {
                        "audios": final_left,
                        "images": final_right,
                        "answer_map": answer_map,
                    }
                else:
                    reconstructed_meta = {
                        "texts": final_left,
                        "images": final_right,
                        "answer_map": answer_map,
                    }

            # B) 对话配对
            elif ex_type_name == "READ_DIALOGUE_MATCH":
                questions, answers = [], []
                for sub_ex in sorted_children:
                    sub_meta = sub_ex.meta or {}
                    questions.append(
                        {
                            "text": sub_meta.get("utterance"),
                            "pinyin": sub_meta.get("utter_pinyin"),
                        }
                    )
                    answers.append(
                        {
                            "text": sub_meta.get("reply"),
                            "pinyin": sub_meta.get("reply_pinyin"),
                        }
                    )

                if not questions or len(questions) != len(answers):
                    continue

                n = len(questions)
                labels = [chr(ord("A") + i) for i in range(n)]
                q_indices, a_indices = list(range(n)), list(range(n))
                rnd.shuffle(q_indices)
                rnd.shuffle(a_indices)

                shuffled_questions = [
                    {"label": labels[i], **questions[q_indices[i]]} for i in range(n)
                ]
                shuffled_answers = [
                    {"label": labels[i], **answers[a_indices[i]]} for i in range(n)
                ]

                # 关键修正(2): 使用与图片配对题一致的、更健壮的答案生成逻辑
                answer_map = {
                    labels[q_indices.index(i)]: labels[a_indices.index(i)] for i in range(n)
                }

                reconstructed_meta = {
                    "shuffled_questions": shuffled_questions,
                    "shuffled_answers": shuffled_answers,
                    "answers": answer_map,
                }

            # 回写父题 meta，并记录
            parent_exercise.meta = reconstructed_meta
            reconstructed_list.append(parent_exercise)
            processed_parent_ids.add(parent_id)

        # 普通题（没有 parent_exercise_id）直接加入
        elif not exercise.parent_exercise_id:
            reconstructed_list.append(exercise)

    return reconstructed_list


def create_exercise_session(
    db: Session,
    request: schemas.ExerciseRequest,
    base_url: Optional[str] = None,          # ← 新增：从路由传入，用于拼绝对 URL
) -> Dict:
    """
    创建一次练习会话的主服务函数。
    """
    try:
        lesson_uuid = uuid.UUID(request.lessonId)
    except ValueError:
        return None

    lesson = crud.get_lesson_context(db, lesson_uuid)
    if not lesson:
        return None

    # 依据期望时长与题型耗时估算目标数量
    avg_duration = _calculate_average_duration(request.exerciseTypes)
    target_count = min(math.ceil(request.duration / avg_duration), MAX_QUESTIONS_LIMIT)
    target_count = max(1, int(target_count))

    # 候选题检索
    candidate_exercises = crud.get_candidate_exercises(
        db,
        lesson_id=request.lessonId,
        exercise_type_names=request.exerciseTypes,
    )

    if not candidate_exercises:
        return {}

    # 配对题重构（并在此阶段把媒体 URL 转为绝对 URL）
    reconstructed_candidates = _reconstruct_matching_exercises(
        db, candidate_exercises, base_url=base_url
    )

    # 去重（以父子重构后的父题为准）
    unique_exercises_dict = {ex.id: ex for ex in reconstructed_candidates}
    unique_candidate_exercises = list(unique_exercises_dict.values())

    # 采样
    if len(unique_candidate_exercises) <= target_count:
        selected_exercises = unique_candidate_exercises
    else:
        selected_exercises = random.sample(unique_candidate_exercises, k=target_count)

    # 统一格式化为对前端友好的结构
    # 传入 base_url，便于 formatter 在其它题型上也把 URL 拼成绝对地址
    try:
        formatted_exercises = format_exercises_for_api(
            selected_exercises,
            base_url=base_url,                      # ← 新增：继续传给 formatter
        )
    except TypeError:
        # 兼容旧签名：如果你尚未修改 formatter 的函数签名，这里会回退到旧用法
        formatted_exercises = format_exercises_for_api(selected_exercises)

    response_data: Dict = {
        "phaseId": str(lesson.topic.phase.id) if lesson.topic and lesson.topic.phase else "UNKNOWN",
        "topicId": str(lesson.topic.id) if lesson.topic else "UNKNOWN",
        "duration": request.duration,
        "count": len(formatted_exercises),
        "sessionId": f"session_{random.randint(1000, 9999)}",
        "exercises": formatted_exercises,
    }
    return response_data
