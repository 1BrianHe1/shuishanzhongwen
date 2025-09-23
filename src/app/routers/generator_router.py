from fastapi import APIRouter, HTTPException
from app.service.exercise_service import (create_listen_image_tf_exercise,GenerateReq,ListenImageTfResp,MCReq,MCResp,create_listen_image_mc_exercise,create_listen_image_match_exercise,MatchReq,MatchResp,
                                          ListenSentenceQAReq,ListenSentenceQAResp,create_listen_sentence_qa_exercise,ListenSentenceTfReq,ListenSentenceTfResp,create_listen_sentence_tf_exercise,
                                          ReadImageTfReq,ReadImageTfResp,create_read_image_tf_exercise,ReadImageMatchReq,ReadImageMatchResp,create_read_image_match_exercise,ReadingDialogMatchReq,ReadingDialogMatchResp,create_reading_dialog_matching,
                                          ReadingGapFillReq,ReadingGapFillResp,create_reading_gap_fill_exercise,SentenceTransReq,SentenceTransResp,create_sentence_translation_exercise,ReadSentenceCompChoReq,ReadSentenceCompChoResp,
                                          create_read_sentence_comprehension_choice_exercise,ReadSentenceTfReq,ReadSentenceTfResp,create_read_sentence_tf_exercise,ReadParagraphComprReq,ReadParagraphComprResp,create_read_paragraph_comprehension_exercise,
                                          WordOrderReq,WordOrderResp,create_word_order_exercise
                                          )
from app.utils.util import _db

router=APIRouter()
@router.post(
    "/api/generate-v2/listen-image-tf", 
    response_model=ListenImageTfResp,
    tags=["Exercise Generation"]
)
async def generate_listen_image_tf_v2(req: GenerateReq):
    """
    生成一个“听录音,看图判断”的题目。
    """
    conn = None
    try:
        conn = _db()
        cur = conn.cursor()
        
        result = await create_listen_image_tf_exercise(cur, req)
        
        conn.commit()
        return result

    except (Exception, ValueError) as e:
        if conn:
            conn.rollback()
        raise HTTPException(status_code=500, detail=f"生成题目时发生错误: {str(e)}")
    finally:
        if conn:
            cur.close()
            conn.close()

@router.post("/api/generate-v2/listen-image-choice", response_model=MCResp,tags=["Exercise Generation"])
async def generate_listen_image_mc(req: MCReq):
    """
    生成【听录音·看图选择（单选）】并落库
    """
    conn = None
    try:
        conn = _db()
        cur = conn.cursor()
        
        # 调用核心业务逻辑函数
        result = await create_listen_image_mc_exercise(cur, req)
        
        conn.commit()
        return result

    except (Exception, ValueError) as e:
        if conn:
            conn.rollback()
        raise HTTPException(status_code=500, detail=f"生成'听录音看图选择'题目时发生错误: {str(e)}")
    finally:
        if conn:
            cur.close()
            conn.close()


@router.post("/api/generate-v2/listen-image-match", response_model=MatchResp,tags=["Exercise Generation"])
async def generate_listen_image_match(req: MatchReq):
    """
    生成听录音，看图配对题目
    """
    conn = None
    try:
        conn = _db()
        cur = conn.cursor()
        
        # 调用核心业务逻辑函数
        result = await create_listen_image_match_exercise(cur, req)
        
        conn.commit()
        return result

    except (Exception, ValueError) as e:
        if conn:
            conn.rollback()
        raise HTTPException(status_code=500, detail=f"生成'听录音看图选择'题目时发生错误: {str(e)}")
    finally:
        if conn:
            cur.close()
            conn.close()


@router.post("/api/generate-v2/listen-sentence-QA", response_model=ListenSentenceQAResp,tags=["Exercise Generation"])
async def generate_listen_sentence_qa(req: ListenSentenceQAReq):
    """
    生成听录音，看图配对题目
    """
    conn = None
    try:
        conn = _db()
        cur = conn.cursor()
        
        # 调用核心业务逻辑函数
        result = await create_listen_sentence_qa_exercise(cur, req)
        
        conn.commit()
        return result

    except (Exception, ValueError) as e:
        if conn:
            conn.rollback()
        raise HTTPException(status_code=500, detail=f"生成'听录音看图选择'题目时发生错误: {str(e)}")
    finally:
        if conn:
            cur.close()
            conn.close()

@router.post("/api/generate-v2/listen-sentence-TF", response_model=ListenSentenceTfResp,tags=["Exercise Generation"])
async def generate_listen_sentence_tf(req: ListenSentenceTfReq):
    """
    生成听录音，看图配对题目
    """
    conn = None
    try:
        conn = _db()
        cur = conn.cursor()
        
        # 调用核心业务逻辑函数
        result = await create_listen_sentence_tf_exercise(cur, req)
        
        conn.commit()
        return result

    except (Exception, ValueError) as e:
        if conn:
            conn.rollback()
        raise HTTPException(status_code=500, detail=f"生成'听录音看图选择'题目时发生错误: {str(e)}")
    finally:
        if conn:
            cur.close()
            conn.close()


@router.post("/api/generate-v2/read-image-TF", response_model=ReadImageTfResp,tags=["Exercise Generation"])
async def generate_read_picture_tf(req: ReadImageTfReq):
    """
    生成听录音，看图配对题目
    """
    conn = None
    try:
        conn = _db()
        cur = conn.cursor()
        
        # 调用核心业务逻辑函数
        result = await create_read_image_tf_exercise(cur, req)
        
        conn.commit()
        return result

    except (Exception, ValueError) as e:
        if conn:
            conn.rollback()
        raise HTTPException(status_code=500, detail=f"生成'听录音看图选择'题目时发生错误: {str(e)}")
    finally:
        if conn:
            cur.close()
            conn.close()



@router.post("/api/generate-v2/read-image-match", response_model=ReadImageMatchResp,tags=["Exercise Generation"])
async def generate_read_picture_match(req: ReadImageMatchReq):
    conn = None
    try:
        conn = _db()
        cur = conn.cursor()
        
        # 调用核心业务逻辑函数
        result = await create_read_image_match_exercise(cur, req)
        
        conn.commit()
        return result

    except (Exception, ValueError) as e:
        if conn:
            conn.rollback()
        raise HTTPException(status_code=500, detail=f"生成'听录音看图选择'题目时发生错误: {str(e)}")
    finally:
        if conn:
            cur.close()
            conn.close()

@router.post("/api/generate-v2/read-dialog-match", response_model=ReadingDialogMatchResp,tags=["Exercise Generation"])
async def generate_read_dialog_match(req: ReadingDialogMatchReq):
    conn = None
    try:
        conn = _db()
        cur = conn.cursor()
        
        # 调用核心业务逻辑函数
        result = await create_reading_dialog_matching(cur, req)
        
        conn.commit()
        return result

    except (Exception, ValueError) as e:
        if conn:
            conn.rollback()
        raise HTTPException(status_code=500, detail=f"生成'听录音看图选择'题目时发生错误: {str(e)}")
    finally:
        if conn:
            cur.close()
            conn.close()

@router.post("/api/generate-v2/read-gap-fill", response_model=ReadingGapFillResp,tags=["Exercise Generation"])
async def generate_read_gap_fill(req: ReadingGapFillReq):
    conn = None
    try:
        conn = _db()
        cur = conn.cursor()
        
        # 调用核心业务逻辑函数
        result = await create_reading_gap_fill_exercise(cur, req)
        
        conn.commit()
        return result

    except (Exception, ValueError) as e:
        if conn:
            conn.rollback()
        raise HTTPException(status_code=500, detail=f"生成'听录音看图选择'题目时发生错误: {str(e)}")
    finally:
        if conn:
            cur.close()
            conn.close()

@router.post("/api/generate-v2/sentence-translate", response_model=SentenceTransResp,tags=["Exercise Generation"])
async def generate_sentence_translation(req: SentenceTransReq):
    conn = None
    try:
        conn = _db()
        cur = conn.cursor()
        
        # 调用核心业务逻辑函数
        result = await create_sentence_translation_exercise(cur, req)
        
        conn.commit()
        return result

    except (Exception, ValueError) as e:
        if conn:
            conn.rollback()
        raise HTTPException(status_code=500, detail=f"生成'听录音看图选择'题目时发生错误: {str(e)}")
    finally:
        if conn:
            cur.close()
            conn.close()

@router.post("/api/generate-v2/read-sentence-comprehension-choice", response_model=ReadSentenceCompChoResp,tags=["Exercise Generation"])
async def generate_read_sentence_comprehension_choice(req: ReadSentenceCompChoReq):
    conn = None
    try:
        conn = _db()
        cur = conn.cursor()
        
        # 调用核心业务逻辑函数
        result = await create_read_sentence_comprehension_choice_exercise(cur, req)
        
        conn.commit()
        return result

    except (Exception, ValueError) as e:
        if conn:
            conn.rollback()
        raise HTTPException(status_code=500, detail=f"生成'听录音看图选择'题目时发生错误: {str(e)}")
    finally:
        if conn:
            cur.close()
            conn.close()

@router.post("/api/generate-v2/read-sentence-comprehension-tf", response_model=ReadSentenceTfResp,tags=["Exercise Generation"])
async def generate_read_sentence_comprehension_tf(req: ReadSentenceTfReq):
    conn = None
    try:
        conn = _db()
        cur = conn.cursor()
        
        # 调用核心业务逻辑函数
        result = await create_read_sentence_tf_exercise(cur, req)
        
        conn.commit()
        return result

    except (Exception, ValueError) as e:
        if conn:
            conn.rollback()
        raise HTTPException(status_code=500, detail=f"生成'听录音看图选择'题目时发生错误: {str(e)}")
    finally:
        if conn:
            cur.close()
            conn.close()

@router.post("/api/generate-v2/read-paragraph-comprehension", response_model=ReadParagraphComprResp,tags=["Exercise Generation"])
async def generate_read_paragraph_comprehension(req:ReadParagraphComprReq):
    conn = None
    try:
        conn = _db()
        cur = conn.cursor()
        

        result = await create_read_paragraph_comprehension_exercise(cur, req)
        
        conn.commit()
        return result

    except (Exception, ValueError) as e:
        if conn:
            conn.rollback()
        raise HTTPException(status_code=500, detail=f"生成'听录音看图选择'题目时发生错误: {str(e)}")
    finally:
        if conn:
            cur.close()
            conn.close()

@router.post("/api/generate-v2/word_order", response_model=WordOrderResp,tags=["Exercise Generation"])
async def generate_word_order(req:WordOrderReq):
    conn = None
    try:
        conn = _db()
        cur = conn.cursor()
        

        result = await create_word_order_exercise(cur, req)
        
        conn.commit()
        return result

    except (Exception, ValueError) as e:
        if conn:
            conn.rollback()
        raise HTTPException(status_code=500, detail=f"生成'听录音看图选择'题目时发生错误: {str(e)}")
    finally:
        if conn:
            cur.close()
            conn.close()












