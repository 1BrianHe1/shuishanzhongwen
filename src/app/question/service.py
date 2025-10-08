# app/question/service.py
import uuid
import json
from typing import List, Dict, Optional, Union
from sqlalchemy.orm import Session
from sqlalchemy import text
from .schemas import (
    SimpleQuestion, SimpleQuestionContent, ListenImageTrueFalseResponse,
    Exercise, ExerciseResponse, TFContent, ChoiceContent, MatchContent, OrderContent,
    Option, MatchItem, OrderItem, SubmitAnswerRequest, SubmitAnswerResponse,
    SubmissionResult
)

def get_exercise_types_from_db(db: Session) -> Dict[str, Dict]:
    """从数据库获取题目类型"""
    try:
        result = db.execute(text("""
            SELECT et.name, et.display_name, et.description, sc.name as skill_category
            FROM content_new.exercise_types et
            JOIN content_new.skill_categories sc ON et.skill_category_id = sc.id
            ORDER BY et.display_order
        """))

        types = result.fetchall()

        # 构建题目类型映射
        type_mapping = {}
        for t in types:
            type_mapping[t.name] = {
                "name": t.display_name,
                "description": t.description,
                "skill_category": t.skill_category,
                "requires_audio": "LISTEN" in t.name,
                "requires_image": "IMAGE" in t.name,
                "has_options": "MC" in t.name or "TRUE_FALSE" in t.name
            }

        return type_mapping
    except Exception as e:
        print(f"获取题目类型失败: {e}")
        # 如果数据库出错，返回空字典
        return {}

def generate_listen_image_true_false_questions(
    count: int,
    db: Session,
    phase_name: Optional[str] = None,
    topic_name: Optional[str] = None,
    lesson_name: Optional[str] = None
) -> ListenImageTrueFalseResponse:
    """生成听录音看图判断题目"""

    # 生成会话ID
    session_id = str(uuid.uuid4())

    # 根据提供的参数选择题目
    if lesson_name or phase_name or topic_name:
        # 构建动态查询条件
        where_conditions = ["et.name = 'LISTEN_IMAGE_TRUE_FALSE'"]
        params = {"limit": count}

        # 添加lesson条件
        if lesson_name:
            where_conditions.append("l.lesson_name = :lesson_name")
            params["lesson_name"] = lesson_name

        # 添加phase条件
        if phase_name:
            where_conditions.append("p.name = :phase_name")
            params["phase_name"] = phase_name

        # 添加topic条件
        if topic_name:
            where_conditions.append("t.topic_name = :topic_name")
            params["topic_name"] = topic_name

        where_clause = " AND ".join(where_conditions)

        query = f"""
            SELECT e.id, e.prompt, e.metadata, e.difficulty_level,
                   et.name as exercise_type_name, et.display_name as exercise_type_display,
                   w.characters, w.pinyin, w.translation
            FROM content_new.lesson_words lw
            JOIN content_new.lessons l ON lw.lesson_id = l.id
            JOIN content_new.topics t ON l.topic_id = t.id
            JOIN content_new.phases p ON t.phase_id = p.id
            JOIN content_new.words w ON lw.word_id = w.id
            JOIN content_new.exercises e ON w.id = e.word_id
            JOIN content_new.exercise_types et ON e.exercise_type_id = et.id
            WHERE {where_clause}
            ORDER BY RANDOM()
            LIMIT :limit
        """

        result = db.execute(text(query), params)
    else:
        # 如果没有提供lessonName，使用原有逻辑
        result = db.execute(text("""
            SELECT e.id, e.prompt, e.metadata, e.difficulty_level,
                   et.name as exercise_type_name, et.display_name as exercise_type_display,
                   w.characters, w.pinyin, w.translation
            FROM content_new.exercises e
            JOIN content_new.exercise_types et ON e.exercise_type_id = et.id
            LEFT JOIN content_new.words w ON e.word_id = w.id
            WHERE et.name = 'LISTEN_IMAGE_TRUE_FALSE'
            ORDER BY RANDOM()
            LIMIT :limit
        """), {"limit": count})

    exercises = []
    for row in result:
        exercise = {
            "id": str(row.id),
            "prompt": row.prompt,
            "metadata": row.metadata,
            "difficulty_level": row.difficulty_level,
            "exercise_type_name": row.exercise_type_name,
            "exercise_type_display": row.exercise_type_display,
            "word_characters": row.characters,
            "word_pinyin": row.pinyin,
            "word_translation": row.translation
        }

        # 获取关联的媒体资源
        media_result = db.execute(text("""
            SELECT ma.file_url, ma.file_type, ma.mime_type, ema.usage_role
            FROM content_new.exercise_media_assets ema
            JOIN content_new.media_assets ma ON ema.media_asset_id = ma.id
            WHERE ema.exercise_id = :exercise_id
        """), {"exercise_id": row.id})

        exercise['media_assets'] = []
        for media_row in media_result:
            exercise['media_assets'].append({
                "file_url": media_row.file_url,
                "file_type": media_row.file_type,
                "mime_type": media_row.mime_type,
                "usage_role": media_row.usage_role
            })

        exercises.append(exercise)

    # 生成题目对象
    questions = []
    for exercise_data in exercises:
        # 使用数据库中的exercise_id作为questionId
        question_id = exercise_data["id"]

        # 解析metadata中的题目数据
        metadata = exercise_data.get('metadata', {})
        if isinstance(metadata, str):
            metadata = json.loads(metadata)

        # 获取媒体资源
        media_assets = exercise_data.get('media_assets', [])
        audio_url = None
        image_url = None

        for asset in media_assets:
            if asset['usage_role'] == 'prompt_audio':
                audio_url = asset['file_url']
            elif asset['usage_role'] in ['stem_image', 'correct_image']:
                image_url = asset['file_url']

        # 构建简化的题目内容
        content = SimpleQuestionContent(
            question=exercise_data.get('prompt', ''),
            audioUrl=audio_url,
            imageUrl=image_url,
            listeningText=metadata.get('listening_text')
        )

        # 获取正确答案
        correct_answer = metadata.get('correct_answer')

        question = SimpleQuestion(
            questionId=question_id,
            questionType="LISTEN_IMAGE_TRUE_FALSE",
            content=content,
            correctAnswer=correct_answer
        )
        questions.append(question)

    # 构建响应
    response = ListenImageTrueFalseResponse(
        count=len(questions),
        sessionId=session_id,
        questions=questions
    )

    return response

# ===========================================
# 提交答案服务
# ===========================================

def submit_answers(submit_request: SubmitAnswerRequest, db: Session) -> SubmitAnswerResponse:
    """提交答案并评分"""

    results = []
    total_score = 0
    correct_count = 0
    total_count = len(submit_request.submission_list)

    for submission in submit_request.submission_list:
        # 从数据库获取正确答案
        result = db.execute(text("""
            SELECT e.metadata
            FROM content_new.exercises e
            WHERE e.id = :exercise_id
        """), {"exercise_id": submission.exerciseId})

        row = result.fetchone()
        if not row:
            # 如果找不到题目，标记为错误
            submission_result = SubmissionResult(
                exerciseId=submission.exerciseId,
                isCorrect=False,
                points=0,
                correctAnswer="题目不存在"
            )
            results.append(submission_result)
            continue

        # 解析metadata获取正确答案
        metadata = row.metadata
        if isinstance(metadata, str):
            metadata = json.loads(metadata)

        correct_answer = metadata.get('correct_answer')

        # 比较答案
        is_correct = _compare_answers(submission.userAnswer, correct_answer)

        # 计算得分
        points = submission.points if submission.points is not None else (1 if is_correct else 0)

        if is_correct:
            correct_count += 1
            total_score += points

        submission_result = SubmissionResult(
            exerciseId=submission.exerciseId,
            isCorrect=is_correct,
            points=points,
            correctAnswer=correct_answer
        )
        results.append(submission_result)

    return SubmitAnswerResponse(
        sessionId=submit_request.sessionId,
        totalScore=total_score,
        correctCount=correct_count,
        totalCount=total_count,
        results=results
    )

def _compare_answers(user_answer: Union[bool, str, List[str], Dict[str, str]],
                    correct_answer: Union[bool, str, List[str], Dict[str, str]]) -> bool:
    """比较用户答案和正确答案"""

    # 布尔值比较（判断题）
    if isinstance(correct_answer, bool):
        return bool(user_answer) == correct_answer

    # 字符串比较（选择题）
    if isinstance(correct_answer, str):
        return str(user_answer) == correct_answer

    # 列表比较（排序题）
    if isinstance(correct_answer, list):
        if not isinstance(user_answer, list):
            return False
        return user_answer == correct_answer

    # 字典比较（配对题）
    if isinstance(correct_answer, dict):
        if not isinstance(user_answer, dict):
            return False
        return user_answer == correct_answer

    return False

# ===========================================
# 各种题型生成服务
# ===========================================

def generate_tf_exercises(
    exercise_type: str,
    count: int,
    db: Session,
    phase_name: Optional[str] = None,
    topic_name: Optional[str] = None,
    lesson_name: Optional[str] = None
) -> List[Exercise]:
    """生成判断题（TF类型）"""

    # 构建查询条件
    where_conditions = [f"et.name = '{exercise_type}'"]
    params = {"limit": count}

    if lesson_name:
        where_conditions.append("l.lesson_name = :lesson_name")
        params["lesson_name"] = lesson_name
    if phase_name:
        where_conditions.append("p.name = :phase_name")
        params["phase_name"] = phase_name
    if topic_name:
        where_conditions.append("t.topic_name = :topic_name")
        params["topic_name"] = topic_name

    where_clause = " AND ".join(where_conditions)

    if lesson_name or phase_name or topic_name:
        query = f"""
            SELECT e.id, e.prompt, e.metadata, e.difficulty_level,
                   et.name as exercise_type_name, et.display_name as exercise_type_display,
                   w.characters, w.pinyin, w.translation
            FROM content_new.lesson_words lw
            JOIN content_new.lessons l ON lw.lesson_id = l.id
            JOIN content_new.topics t ON l.topic_id = t.id
            JOIN content_new.phases p ON t.phase_id = p.id
            JOIN content_new.words w ON lw.word_id = w.id
            JOIN content_new.exercises e ON w.id = e.word_id
            JOIN content_new.exercise_types et ON e.exercise_type_id = et.id
            WHERE {where_clause}
            ORDER BY RANDOM()
            LIMIT :limit
        """
    else:
        query = f"""
            SELECT e.id, e.prompt, e.metadata, e.difficulty_level,
                   et.name as exercise_type_name, et.display_name as exercise_type_display,
                   w.characters, w.pinyin, w.translation
            FROM content_new.exercises e
            JOIN content_new.exercise_types et ON e.exercise_type_id = et.id
            LEFT JOIN content_new.words w ON e.word_id = w.id
            WHERE {where_clause}
            ORDER BY RANDOM()
            LIMIT :limit
        """

    result = db.execute(text(query), params)
    exercises = []

    for row in result:
        # 获取媒体资源
        media_result = db.execute(text("""
            SELECT ma.file_url, ma.file_type, ma.mime_type, ema.usage_role
            FROM content_new.exercise_media_assets ema
            JOIN content_new.media_assets ma ON ema.media_asset_id = ma.id
            WHERE ema.exercise_id = :exercise_id
        """), {"exercise_id": row.id})

        media_assets = {}
        for media_row in media_result:
            media_assets[media_row.usage_role] = media_row.file_url

        # 解析metadata
        metadata = row.metadata
        if isinstance(metadata, str):
            metadata = json.loads(metadata)

        # 构建TF题目内容
        content = TFContent(
            prompt=row.prompt or "请判断以下陈述是否正确。",
            audioUrl=media_assets.get('prompt_audio'),
            listeningText=metadata.get('listening_text'),
            imageUrl=media_assets.get('stem_image') or media_assets.get('correct_image'),
            statement=metadata.get('statement'),
            passage=metadata.get('passage')
        )

        exercise = Exercise(
            exerciseId=str(row.id),
            exerciseType=exercise_type,
            content=content,
            correctAnswer=metadata.get('correct_answer', True)
        )
        exercises.append(exercise)

    return exercises

def generate_choice_exercises(
    exercise_type: str,
    count: int,
    db: Session,
    phase_name: Optional[str] = None,
    topic_name: Optional[str] = None,
    lesson_name: Optional[str] = None
) -> List[Exercise]:
    """生成选择题（Choice类型）"""

    # 构建查询条件
    where_conditions = [f"et.name = '{exercise_type}'"]
    params = {"limit": count}

    if lesson_name:
        where_conditions.append("l.lesson_name = :lesson_name")
        params["lesson_name"] = lesson_name
    if phase_name:
        where_conditions.append("p.name = :phase_name")
        params["phase_name"] = phase_name
    if topic_name:
        where_conditions.append("t.topic_name = :topic_name")
        params["topic_name"] = topic_name

    where_clause = " AND ".join(where_conditions)

    if lesson_name or phase_name or topic_name:
        query = f"""
            SELECT e.id, e.prompt, e.metadata, e.difficulty_level,
                   et.name as exercise_type_name, et.display_name as exercise_type_display,
                   w.characters, w.pinyin, w.translation
            FROM content_new.lesson_words lw
            JOIN content_new.lessons l ON lw.lesson_id = l.id
            JOIN content_new.topics t ON l.topic_id = t.id
            JOIN content_new.phases p ON t.phase_id = p.id
            JOIN content_new.words w ON lw.word_id = w.id
            JOIN content_new.exercises e ON w.id = e.word_id
            JOIN content_new.exercise_types et ON e.exercise_type_id = et.id
            WHERE {where_clause}
            ORDER BY RANDOM()
            LIMIT :limit
        """
    else:
        query = f"""
            SELECT e.id, e.prompt, e.metadata, e.difficulty_level,
                   et.name as exercise_type_name, et.display_name as exercise_type_display,
                   w.characters, w.pinyin, w.translation
            FROM content_new.exercises e
            JOIN content_new.exercise_types et ON e.exercise_type_id = et.id
            LEFT JOIN content_new.words w ON e.word_id = w.id
            WHERE {where_clause}
            ORDER BY RANDOM()
            LIMIT :limit
        """

    result = db.execute(text(query), params)
    exercises = []

    for row in result:
        # 获取媒体资源
        media_result = db.execute(text("""
            SELECT ma.file_url, ma.file_type, ma.mime_type, ema.usage_role
            FROM content_new.exercise_media_assets ema
            JOIN content_new.media_assets ma ON ema.media_asset_id = ma.id
            WHERE ema.exercise_id = :exercise_id
        """), {"exercise_id": row.id})

        media_assets = {}
        for media_row in media_result:
            media_assets[media_row.usage_role] = media_row.file_url

        # 解析metadata
        metadata = row.metadata
        if isinstance(metadata, str):
            metadata = json.loads(metadata)

        # 构建选项
        options = []
        metadata_options = metadata.get('options', [])
        for i, option_data in enumerate(metadata_options):
            if isinstance(option_data, dict):
                option = Option(
                    label=option_data.get('label', chr(65 + i)),  # A, B, C, D
                    text=option_data.get('text'),
                    imageUrl=option_data.get('imageUrl'),
                    pinyin=option_data.get('pinyin')
                )
            else:
                # 简单字符串选项
                option = Option(
                    label=chr(65 + i),  # A, B, C, D
                    text=str(option_data)
                )
            options.append(option)

        # 构建Choice题目内容
        content = ChoiceContent(
            prompt=row.prompt or "请选择正确答案。",
            audioUrl=media_assets.get('prompt_audio'),
            listeningText=metadata.get('listening_text'),
            imageUrl=media_assets.get('stem_image'),
            passage=metadata.get('passage'),
            question=metadata.get('question'),
            options=options
        )

        exercise = Exercise(
            exerciseId=str(row.id),
            exerciseType=exercise_type,
            content=content,
            correctAnswer=metadata.get('correct_answer', 'A')
        )
        exercises.append(exercise)

    return exercises

def generate_match_exercises(
    exercise_type: str,
    count: int,
    db: Session,
    phase_name: Optional[str] = None,
    topic_name: Optional[str] = None,
    lesson_name: Optional[str] = None
) -> List[Exercise]:
    """生成配对题（Match类型）"""

    # 构建查询条件
    where_conditions = [f"et.name = '{exercise_type}'"]
    params = {"limit": count}

    if lesson_name:
        where_conditions.append("l.lesson_name = :lesson_name")
        params["lesson_name"] = lesson_name
    if phase_name:
        where_conditions.append("p.name = :phase_name")
        params["phase_name"] = phase_name
    if topic_name:
        where_conditions.append("t.topic_name = :topic_name")
        params["topic_name"] = topic_name

    where_clause = " AND ".join(where_conditions)

    if lesson_name or phase_name or topic_name:
        query = f"""
            SELECT e.id, e.prompt, e.metadata, e.difficulty_level,
                   et.name as exercise_type_name, et.display_name as exercise_type_display,
                   w.characters, w.pinyin, w.translation
            FROM content_new.lesson_words lw
            JOIN content_new.lessons l ON lw.lesson_id = l.id
            JOIN content_new.topics t ON l.topic_id = t.id
            JOIN content_new.phases p ON t.phase_id = p.id
            JOIN content_new.words w ON lw.word_id = w.id
            JOIN content_new.exercises e ON w.id = e.word_id
            JOIN content_new.exercise_types et ON e.exercise_type_id = et.id
            WHERE {where_clause}
            ORDER BY RANDOM()
            LIMIT :limit
        """
    else:
        query = f"""
            SELECT e.id, e.prompt, e.metadata, e.difficulty_level,
                   et.name as exercise_type_name, et.display_name as exercise_type_display,
                   w.characters, w.pinyin, w.translation
            FROM content_new.exercises e
            JOIN content_new.exercise_types et ON e.exercise_type_id = et.id
            LEFT JOIN content_new.words w ON e.word_id = w.id
            WHERE {where_clause}
            ORDER BY RANDOM()
            LIMIT :limit
        """

    result = db.execute(text(query), params)
    exercises = []

    for row in result:
        # 解析metadata
        metadata = row.metadata
        if isinstance(metadata, str):
            metadata = json.loads(metadata)

        # 构建左侧项目
        left_items = []
        for item_data in metadata.get('leftItems', []):
            item = MatchItem(
                label=item_data.get('label'),
                text=item_data.get('text'),
                audioUrl=item_data.get('audioUrl'),
                imageUrl=item_data.get('imageUrl'),
                listeningText=item_data.get('listeningText'),
                pinyin=item_data.get('pinyin')
            )
            left_items.append(item)

        # 构建右侧项目
        right_items = []
        for item_data in metadata.get('rightItems', []):
            item = MatchItem(
                label=item_data.get('label'),
                text=item_data.get('text'),
                audioUrl=item_data.get('audioUrl'),
                imageUrl=item_data.get('imageUrl'),
                listeningText=item_data.get('listeningText'),
                pinyin=item_data.get('pinyin')
            )
            right_items.append(item)

        # 构建Match题目内容
        content = MatchContent(
            prompt=row.prompt or "请进行配对。",
            leftItems=left_items,
            rightItems=right_items
        )

        exercise = Exercise(
            exerciseId=str(row.id),
            exerciseType=exercise_type,
            content=content,
            correctAnswer=metadata.get('correct_answer', {})
        )
        exercises.append(exercise)

    return exercises

def generate_order_exercises(
    exercise_type: str,
    count: int,
    db: Session,
    phase_name: Optional[str] = None,
    topic_name: Optional[str] = None,
    lesson_name: Optional[str] = None
) -> List[Exercise]:
    """生成排序题（Order类型）"""

    # 构建查询条件
    where_conditions = [f"et.name = '{exercise_type}'"]
    params = {"limit": count}

    if lesson_name:
        where_conditions.append("l.lesson_name = :lesson_name")
        params["lesson_name"] = lesson_name
    if phase_name:
        where_conditions.append("p.name = :phase_name")
        params["phase_name"] = phase_name
    if topic_name:
        where_conditions.append("t.topic_name = :topic_name")
        params["topic_name"] = topic_name

    where_clause = " AND ".join(where_conditions)

    if lesson_name or phase_name or topic_name:
        query = f"""
            SELECT e.id, e.prompt, e.metadata, e.difficulty_level,
                   et.name as exercise_type_name, et.display_name as exercise_type_display,
                   w.characters, w.pinyin, w.translation
            FROM content_new.lesson_words lw
            JOIN content_new.lessons l ON lw.lesson_id = l.id
            JOIN content_new.topics t ON l.topic_id = t.id
            JOIN content_new.phases p ON t.phase_id = p.id
            JOIN content_new.words w ON lw.word_id = w.id
            JOIN content_new.exercises e ON w.id = e.word_id
            JOIN content_new.exercise_types et ON e.exercise_type_id = et.id
            WHERE {where_clause}
            ORDER BY RANDOM()
            LIMIT :limit
        """
    else:
        query = f"""
            SELECT e.id, e.prompt, e.metadata, e.difficulty_level,
                   et.name as exercise_type_name, et.display_name as exercise_type_display,
                   w.characters, w.pinyin, w.translation
            FROM content_new.exercises e
            JOIN content_new.exercise_types et ON e.exercise_type_id = et.id
            LEFT JOIN content_new.words w ON e.word_id = w.id
            WHERE {where_clause}
            ORDER BY RANDOM()
            LIMIT :limit
        """

    result = db.execute(text(query), params)
    exercises = []

    for row in result:
        # 解析metadata
        metadata = row.metadata
        if isinstance(metadata, str):
            metadata = json.loads(metadata)

        # 构建词语或句子列表
        words = None
        sentences = None

        if 'words' in metadata:
            words = []
            for word_data in metadata['words']:
                item = OrderItem(
                    label=word_data.get('label'),
                    word=word_data.get('word'),
                    pinyin=word_data.get('pinyin')
                )
                words.append(item)

        if 'sentences' in metadata:
            sentences = []
            for sentence_data in metadata['sentences']:
                item = OrderItem(
                    label=sentence_data.get('label'),
                    sentence=sentence_data.get('sentence'),
                    pinyin=sentence_data.get('pinyin')
                )
                sentences.append(item)

        # 构建Order题目内容
        content = OrderContent(
            prompt=row.prompt or "请按正确顺序排列。",
            words=words,
            sentences=sentences
        )

        exercise = Exercise(
            exerciseId=str(row.id),
            exerciseType=exercise_type,
            content=content,
            correctAnswer=metadata.get('correct_answer', [])
        )
        exercises.append(exercise)

    return exercises

def generate_exercises_by_types(
    exercise_types: List[str],
    count: int,
    db: Session,
    phase_name: Optional[str] = None,
    topic_name: Optional[str] = None,
    lesson_name: Optional[str] = None
) -> ExerciseResponse:
    """根据题型列表生成题目"""

    session_id = str(uuid.uuid4())
    all_exercises = []

    # 计算每种题型的数量
    count_per_type = max(1, count // len(exercise_types))
    remaining_count = count - (count_per_type * len(exercise_types))

    for i, exercise_type in enumerate(exercise_types):
        # 为最后一种题型添加剩余的数量
        current_count = count_per_type
        if i == len(exercise_types) - 1:
            current_count += remaining_count

        # 根据题型选择生成函数
        if 'TRUE_FALSE' in exercise_type or 'TF' in exercise_type:
            exercises = generate_tf_exercises(
                exercise_type, current_count, db, phase_name, topic_name, lesson_name
            )
        elif 'MC' in exercise_type or 'CHOICE' in exercise_type:
            exercises = generate_choice_exercises(
                exercise_type, current_count, db, phase_name, topic_name, lesson_name
            )
        elif 'MATCH' in exercise_type:
            exercises = generate_match_exercises(
                exercise_type, current_count, db, phase_name, topic_name, lesson_name
            )
        elif 'ORDER' in exercise_type:
            exercises = generate_order_exercises(
                exercise_type, current_count, db, phase_name, topic_name, lesson_name
            )
        else:
            # 默认使用TF生成
            exercises = generate_tf_exercises(
                exercise_type, current_count, db, phase_name, topic_name, lesson_name
            )

        all_exercises.extend(exercises)

    return ExerciseResponse(
        phaseId=phase_name,
        topicId=topic_name,
        duration=None,
        count=len(all_exercises),
        sessionId=session_id,
        exercises=all_exercises
    )