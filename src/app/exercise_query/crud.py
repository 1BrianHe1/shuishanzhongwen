
import uuid # [新增] 导入 uuid 库
from typing import List,Optional
from sqlalchemy.orm import Session, joinedload
from . import models
def get_lesson_context(db: Session, lesson_id: uuid.UUID) -> Optional[models.Lesson]:
    """
    根据给定的 lesson_id，高效地查询 Lesson 对象及其关联的 Topic 和 Phase。
    使用 joinedload 可以通过一次数据库查询就获取所有需要的信息。
    """
    return db.query(models.Lesson)\
        .options(
            # 预加载 Lesson.topic，并继续预加载 Topic.phase
            joinedload(models.Lesson.topic).joinedload(models.Topic.phase)
        )\
        .filter(models.Lesson.id == lesson_id)\
        .first()

def get_candidate_exercises(db: Session, lesson_id: str, exercise_type_names: List[str]) -> List[models.Exercise]:
    """
    根据课程ID和题型名称，从数据库高效地查询所有符合条件的题目及其关联数据。
    """
    try:
        lesson_uuid = uuid.UUID(lesson_id)
    except ValueError:
        return []

    word_ids_query = db.query(models.LessonWord.word_id).filter(models.LessonWord.lesson_id == lesson_uuid)
    word_ids = [item[0] for item in word_ids_query.all()]
    if not word_ids:
        return []

    type_ids_query = db.query(models.ExerciseType.id).filter(models.ExerciseType.name.in_(exercise_type_names))
    type_ids = [item[0] for item in type_ids_query.all()]
    if not type_ids:
        return []

    candidate_exercises = db.query(models.Exercise)\
        .options(
            joinedload(models.Exercise.type),
            joinedload(models.Exercise.media_links).joinedload(models.ExerciseMediaAsset.media_asset)
        )\
        .filter(models.Exercise.word_id.in_(word_ids))\
        .filter(models.Exercise.exercise_type_id.in_(type_ids))\
        .all()
        
    return candidate_exercises

def get_parent_exercise_with_all_children(db: Session, parent_id: uuid.UUID) -> Optional[models.Exercise]:
    """
    根据父题ID，一次性高效查询父题及其所有子题和相关的媒体资源。
    """
    return db.query(models.Exercise).options(
        joinedload(models.Exercise.children).options(
            joinedload(models.Exercise.media_links).joinedload(models.ExerciseMediaAsset.media_asset)
        )
    ).filter(models.Exercise.id == parent_id).first()