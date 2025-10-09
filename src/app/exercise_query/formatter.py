# file: question/formatter.py

from typing import List
from . import models
from . import schemas

def _build_media_map(exercise: models.Exercise) -> dict:
    """辅助函数，从业exercise.media_links构建一个usage_role -> URL的字典"""
    if not exercise.media_links:
        return {}
    return {
        link.usage_role: f"/media/{link.media_asset.file_url}"
        for link in exercise.media_links if link.media_asset
    }

def format_exercises_for_api(exercises: List[models.Exercise]) -> List[schemas.AnyExercise]:
    """将ORM模型对象列表，格式化为Pydantic响应模型列表"""
    formatted_list = []
    
    for exercise in exercises:
        ex_type = exercise.type.name if exercise.type else "UNKNOWN"
        metadata = exercise.meta or {}
        media_map = _build_media_map(exercise)
     

        if ex_type == "LISTEN_IMAGE_TRUE_FALSE":
            content = schemas.ListenImageTrueFalseContent(
                prompt=exercise.prompt or "",
                audioUrl=media_map.get('prompt_audio'),
                listeningText=metadata.get("listening_text", ""),
                imageUrl=media_map.get('stem_image')
            )
            formatted_list.append(schemas.ListenImageTrueFalseExercise(
                exerciseId=str(exercise.id), exerciseType=ex_type, content=content,
                correctAnswer=metadata.get("correct_answer", False)
            ))

        elif ex_type == "READ_IMAGE_TRUE_FALSE":
            content = schemas.ReadImageTrueFalseContent(
                prompt=exercise.prompt or "",
                statement=metadata.get("word", ""), # 假设判断用的词在metadata.word里
                imageUrl=media_map.get('stem_image')
            )
            formatted_list.append(schemas.ReadImageTrueFalseExercise(
                exerciseId=str(exercise.id), exerciseType=ex_type, content=content,
                correctAnswer=metadata.get("correct_answer", False)
            ))

        elif ex_type == "LISTEN_SENTENCE_TF":
            content = schemas.ListenSentenceTfContent(
                prompt=exercise.prompt or "",
                audioUrl=media_map.get('prompt_audio'),
                listeningText=metadata.get("listening_text", ""),
                statement=metadata.get("statement", "")
            )
            formatted_list.append(schemas.ListenSentenceTfExercise(
                exerciseId=str(exercise.id), exerciseType=ex_type, content=content,
                correctAnswer=metadata.get("correct_answer", False)
            ))
            
        elif ex_type == "READ_SENTENCE_TF":
            content = schemas.ReadSentenceTfContent(
                prompt=exercise.prompt or "",
                passage=metadata.get("passage", ""),
                statement=metadata.get("statement", "")
            )
            formatted_list.append(schemas.ReadSentenceTfExercise(
                exerciseId=str(exercise.id), exerciseType=ex_type, content=content,
                correctAnswer=metadata.get("correct_answer", False)
            ))

        elif ex_type == "LISTEN_IMAGE_MC":
            options = [
                schemas.McOptionImage(label=opt.get("label"), imageUrl=media_map.get(f'option_image_{opt.get("label")}'))
                for opt in metadata.get("options", [])
            ]
            content = schemas.ListenImageMcContent(
                prompt=exercise.prompt or "", audioUrl=media_map.get('prompt_audio'),
                listeningText=metadata.get("listening_text", ""), options=options
            )
            formatted_list.append(schemas.ListenImageMcExercise(
                exerciseId=str(exercise.id), exerciseType=ex_type, content=content,
                correctAnswer=metadata.get("correct_answer", "")
            ))

        elif ex_type in ["LISTEN_SENTENCE_QA", "READ_SENTENCE_COMPREHENSION_CHOICE", "READ_WORD_GAP_FILL"]:
            options = [schemas.McOptionText(**opt) for opt in metadata.get("options", [])]
            if ex_type == "LISTEN_SENTENCE_QA":
                content = schemas.ListenSentenceQaContent(
                    prompt=exercise.prompt or "", audioUrl=media_map.get('prompt_audio'),
                    listeningText=metadata.get("listening_text", ""), question=metadata.get("question", ""), options=options
                )
                formatted_list.append(schemas.ListenSentenceQaExercise(
                    exerciseId=str(exercise.id), exerciseType=ex_type, content=content, correctAnswer=metadata.get("correct_label", "")
                ))
            elif ex_type == "READ_SENTENCE_COMPREHENSION_CHOICE":
                content = schemas.ReadSentenceComprehensionChoiceContent(
                    prompt=exercise.prompt or "", passage=metadata.get("passage", ""),
                    question=metadata.get("question", ""), options=options
                )
                formatted_list.append(schemas.ReadSentenceComprehensionChoiceExercise(
                    exerciseId=str(exercise.id), exerciseType=ex_type, content=content, correctAnswer=metadata.get("correct_label", "")
                ))
            elif ex_type == "READ_WORD_GAP_FILL":
                content = schemas.ReadWordGapFillContent(
                    prompt=exercise.prompt or "", question=metadata.get("sentence_with_blank", ""), options=options
                )
                formatted_list.append(schemas.ReadWordGapFillExercise(
                    exerciseId=str(exercise.id), exerciseType=ex_type, content=content, correctAnswer=metadata.get("correct_label", "")
                ))

        elif ex_type in ["LISTEN_IMAGE_MATCH", "READ_IMAGE_MATCH", "READ_DIALOGUE_MATCH"]:
            # 注意: 此处假设 service 层创建的 metadata 中已包含 audios/images/texts 等打乱后的数据
            if ex_type == "LISTEN_IMAGE_MATCH":
                left = [schemas.MatchItemAudio(**item) for item in metadata.get("audios", [])]
                right = [schemas.MatchItemImage(**item) for item in metadata.get("images", [])]
                content = schemas.ListenImageMatchContent(prompt=exercise.prompt or "", leftItems=left, rightItems=right)
                formatted_list.append(schemas.ListenImageMatchExercise(
                    exerciseId=str(exercise.id), exerciseType=ex_type, content=content, correctAnswer=metadata.get("answer_map", {})
                ))
            elif ex_type == "READ_IMAGE_MATCH":
                left = [schemas.MatchItemText(**item) for item in metadata.get("texts", [])]
                right = [schemas.MatchItemImage(**item) for item in metadata.get("images", [])]
                content = schemas.ReadImageMatchContent(prompt=exercise.prompt or "", leftItems=left, rightItems=right)
                formatted_list.append(schemas.ReadImageMatchExercise(
                    exerciseId=str(exercise.id), exerciseType=ex_type, content=content, correctAnswer=metadata.get("answer_map", {})
                ))
            elif ex_type == "READ_DIALOGUE_MATCH":
                left = [schemas.MatchItemText(**item) for item in metadata.get("shuffled_questions", [])]
                right = [schemas.MatchItemText(**item) for item in metadata.get("shuffled_answers", [])]
                content = schemas.ReadDialogueMatchContent(prompt=exercise.prompt or "", leftItems=left, rightItems=right)
                formatted_list.append(schemas.ReadDialogueMatchExercise(
                    exerciseId=str(exercise.id), exerciseType=ex_type, content=content, correctAnswer=metadata.get("answers", {})
                ))

        elif ex_type == "READ_WORD_ORDER":
            meta = metadata or {}
            label_map = meta.get("pieces_shuffled_label_map", None)

            shuffled_list = meta.get("pieces_shuffled", None)

            answer_ids = meta.get("answer_ids", None)          
            answer_order = meta.get("answer_order", None)    
            items = []
            correct_answer_numeric = []

            if label_map:
                labels = sorted(label_map.keys()) 
                label_to_numeric = {lab: str(i+1) for i, lab in enumerate(labels)} 
                id_to_numeric = {}

                for i, lab in enumerate(labels, start=1):
                    piece = label_map.get(lab, {}) or {}
                    pid = piece.get("id") or ""
                    txt = piece.get("text", "")
                    id_to_numeric[pid] = str(i)
                    items.append(
                        schemas.WordOrderItem(
                            label=str(i),
                            **{"word/sentence": txt}
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
                        **{"word/sentence": txt}
                        )
                    )
                if answer_ids:
                    correct_answer_numeric = [id_to_numeric.get(pid, "") for pid in answer_ids]
                    correct_answer_numeric = [x for x in correct_answer_numeric if x]
                elif answer_order:
                    labels = [chr(ord('A') + i) for i in range(len(shuffled_list))]
                    label_to_numeric = {lab: str(i+1) for i, lab in enumerate(labels)}
                    correct_answer_numeric = [label_to_numeric.get(lab, "") for lab in answer_order]
                    correct_answer_numeric = [x for x in correct_answer_numeric if x]

            prompt_text = (exercise.prompt or meta.get("sentence") or "请将下列词语按正确顺序排列成句。")

            content = schemas.ReadWordOrderContent(
                prompt=prompt_text,
                **{"words/sentences": items}
            )
            formatted_list.append(
                schemas.ReadWordOrderExercise(
                    exerciseId=str(exercise.id),
                    exerciseType=ex_type,
                    content=content,
                    correctAnswer=correct_answer_numeric
                )
            )

    return formatted_list