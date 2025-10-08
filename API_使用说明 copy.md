# 题目生成API使用说明

## API概述

实现了一个符合要求的前端请求后返回题目的接口，支持多种题目类型的生成和返回。

## 主要接口

### 1. 生成题目集合

**接口地址**: `POST /api/questions/generate`

**请求参数**:
```json
{
    "phaseId": 1,
    "topicId": 1,
    "duration": 1800,
    "questionTypes": ["listening_comprehension", "reading_comprehension"],
    "userId": "可选",
    "token": "可选",
    "count": 10
}
```

**参数说明**:
- `phaseId`: 阶段ID
- `topicId`: 主题ID
- `duration`: 持续时间（秒）
- `questionTypes`: 题目类型列表
- `userId`: 用户ID（可选）
- `token`: 用户token（可选）
- `count`: 题目数量（默认10题）

**返回数据**:
```json
{
    "phase": 1,
    "topic": 1,
    "count": 10,
    "sessionId": "会话唯一标识",
    "duration": 1800,
    "token": "用户token",
    "questions": [
        {
            "questionId": "q_001_listening",
            "questionType": "listening_comprehension",
            "content": {
                "question": "根据录音内容，说话人主要在讨论什么？",
                "audioUrl": "https://example.com/audio/audio1.mp3",
                "options": [
                    "A.讨论工作安排",
                    "B.谈论天气",
                    "C.制定旅行计划",
                    "D.商讨学习计划"
                ],
                "correctAnswer": 0
            }
        }
    ]
}
```

### 2. 获取题目类型

**接口地址**: `GET /api/questions/types`

**返回数据**:
```json
{
    "questionTypes": [
        {
            "type": "listening_comprehension",
            "name": "听力理解",
            "requiresAudio": true,
            "requiresImage": false,
            "hasOptions": true
        }
    ]
}
```

## 支持的题目类型

1. **listening_comprehension** - 听力理解
   - 需要音频文件
   - 包含选择题选项

2. **reading_comprehension** - 阅读理解
   - 纯文本题目
   - 包含选择题选项

3. **listening_image_tf** - 听录音看图判断
   - 需要音频和图片
   - 判断题（正确/错误）

4. **vocabulary_choice** - 词汇选择
   - 纯文本题目
   - 包含选择题选项

## 数据结构说明

### QuestionContent结构
- `question`: 题目文本
- `audioUrl`: 音频URL（听力题目）
- `imageUrl`: 图片URL（看图题目）
- `options`: 选择题选项数组
- `correctAnswer`: 正确答案索引
- `correctAnswers`: 多选题正确答案索引数组
- `correctText`: 填空/问答题正确答案文本

## 使用示例

```python
import requests

# 请求题目
request_data = {
    "phaseId": 1,
    "topicId": 1,
    "duration": 1800,
    "questionTypes": ["listening_comprehension", "reading_comprehension"],
    "count": 10
}

response = requests.post(
    "http://localhost:8000/api/questions/generate",
    json=request_data
)

result = response.json()
print(f"生成了 {result['count']} 道题目")
print(f"会话ID: {result['sessionId']}")
```

## 启动服务

```bash
cd src/app
uvicorn main:app --reload
```

服务启动后访问: http://localhost:8000/docs 查看自动生成的API文档。