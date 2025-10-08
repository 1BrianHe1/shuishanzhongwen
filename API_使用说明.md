# 中文学习平台题目生成API使用说明

## API概述

本系统提供了完整的中文学习题目生成API，支持多种题目类型的生成和返回。系统采用模块化设计，所有题目相关功能都集中在 `question` 模块中。

根据题目设计文档要求，系统支持以下功能：
- 获取各种类型的题目
- 提交答案并获取评分
- 支持按课程、阶段、主题筛选题目
- 完整的题型覆盖（判断题、选择题、配对题、排序题）

## 核心接口

### 1. 生成题目集合

**接口地址**: `POST /api/questions/generate`

**功能描述**: 根据题目设计文档要求，生成指定类型和数量的题目集合。

**请求参数**:
```json
{
  "lessonId": "12312",
  "duration": 1800,
  "exerciseTypes": ["LISTEN_IMAGE_TRUE_FALSE", "READ_SENTENCE_TF"],
  "token": "",
  "count": 5,
  "phaseName": "1A",
  "topicName": "生活",
  "lessonName": "性格"
}
```

**参数说明**:
- `lessonId`: 课程ID（可选）
- `duration`: 持续时间（秒，可选）
- `exerciseTypes`: 题目类型列表（可选，默认使用LISTEN_IMAGE_TRUE_FALSE）
- `token`: 用户token（可选）
- `count`: 题目数量，默认1题
- `phaseName`: 阶段名称（可选，如：1A、2A等）
- `topicName`: 主题名称（可选，如：生活、学校、职业等）
- `lessonName`: 课程名称（可选，如：性格、我的班级、父母职业等）

**返回数据**:
```json
{
  "phaseId": "1A",
  "topicId": "生活",
  "duration": 1800,
  "count": 2,
  "sessionId": "标识，提交答案时使用",
  "exercises": [
    {
      "exerciseId": "q001",
      "exerciseType": "LISTEN_IMAGE_TRUE_FALSE",
      "content": {
        "prompt": "请听录音，再看图片，判断陈述是否正确。",
        "audioUrl": "audios/2025/09/23/53/53607e37eb60.wav",
        "listeningText": "同学在教室里看书。",
        "imageUrl": "images/2025/09/23/3d/3dac5accc39635.png",
        "statement": null,
        "passage": null
      },
      "correctAnswer": true
    }
  ]
}
```

### 2. 提交答案

**接口地址**: `POST /api/questions/submit`

**功能描述**: 提交用户答案并获取评分结果。

**请求参数**:
```json
{
  "sessionId": "12312",
  "token": "",
  "submission_list": [
    {"exerciseId": "q101", "userAnswer": true, "points": 3, "wrongAttempts": 0}
  ]
}
```

**参数说明**:
- `sessionId`: 会话ID（从生成题目接口获取）
- `token`: 用户token（可选）
- `submission_list`: 提交的答案列表
  - `exerciseId`: 题目ID
  - `userAnswer`: 用户答案（布尔值/字符串/数组/对象，根据题型而定）
  - `points`: 用户设定的分值（可选）
  - `wrongAttempts`: 错误尝试次数（可选）

**返回数据**:
```json
{
  "sessionId": "12312",
  "totalScore": 8,
  "correctCount": 2,
  "totalCount": 3,
  "results": [
    {
      "exerciseId": "q101",
      "isCorrect": true,
      "points": 3,
      "correctAnswer": true
    }
  ]
}
```

### 3. 听录音看图判断题目（兼容接口）

**接口地址**: `POST /api/questions/listen-image-true-false`

**功能描述**: 生成听录音看图判断对错的题目，适用于听力理解和视觉理解相结合的练习。

**请求参数**:
```json
{
    "count": 2,
    "userId": "test_user",
    "token": "test_token",
    "phaseName": "初级",
    "topicName": "生活",
    "lessonName": "性格"
}
```

**参数说明**:
- `count`: 题目数量，默认1题
- `userId`: 用户ID（可选）
- `token`: 用户token（可选）
- `phaseName`: 阶段名称（可选，如：初级、1A、2A等）
- `topicName`: 主题名称（可选，如：生活、学校、职业等）
- `lessonName`: 课程名称（可选，如：性格、我的班级、父母职业等）

**返回数据**:
```json
{
    "count": 1,
    "sessionId": "d0a3f49a-4913-4e0c-b311-f28bbdec2944",
    "questions": [
        {
            "questionId": "1fe2d43b-0fae-49ba-8650-8f8321e7604f",
            "questionType": "LISTEN_IMAGE_TRUE_FALSE",
            "content": {
                "question": "请听录音，再看图片，判断陈述是否正确。",
                "audioUrl": "audios/2025/09/23/53/53607e37fd79709c0085c518fcd056b22879e0f62c73693158a4ef935369eb60.wav",
                "imageUrl": "images/2025/09/23/3d/3dac5accb1c2cc3fefef44229681568b06d63e883766de422d1c61e912c39635.png",
                "listeningText": "同学在教室里看书。"
            },
            "correctAnswer": 1
        }
    ]
}
```

### 2. 获取题目类型

**接口地址**: `GET /api/questions/types`

**功能描述**: 获取系统支持的所有题目类型及其配置信息。

**返回数据**:
```json
{
    "questionTypes": [
        {
            "type": "LISTEN_IMAGE_TRUE_FALSE",
            "name": "听录音，看图判断",
            "requiresAudio": true,
            "requiresImage": true,
            "hasOptions": true,
            "description": null,
            "skillCategory": "听力"
        },
        {
            "type": "LISTEN_IMAGE_MC",
            "name": "听录音，看图选择",
            "requiresAudio": true,
            "requiresImage": true,
            "hasOptions": true,
            "description": null,
            "skillCategory": "听力"
        }
    ]
}
```

### 4. 获取题目类型

**接口地址**: `GET /api/questions/types`

**功能描述**: 获取系统支持的所有题目类型及其配置信息。

## 分类接口（按题型）

### 判断题接口

#### 听音看图判断题
- **接口**: `POST /api/questions/tf/listen-image`
- **题型**: LISTEN_IMAGE_TRUE_FALSE
- **说明**: 听录音，再看图片，判断陈述是否正确

#### 读词看图判断题
- **接口**: `POST /api/questions/tf/read-image`
- **题型**: READ_IMAGE_TRUE_FALSE
- **说明**: 阅读词语，再看图片，判断是否匹配

#### 听音看句判断题
- **接口**: `POST /api/questions/tf/listen-sentence`
- **题型**: LISTEN_SENTENCE_TF
- **说明**: 听录音，判断陈述是否正确

#### 阅读判断题
- **接口**: `POST /api/questions/tf/read-sentence`
- **题型**: READ_SENTENCE_TF
- **说明**: 看文章，判断陈述是否正确

### 选择题接口

#### 听音选图题
- **接口**: `POST /api/questions/choice/listen-image`
- **题型**: LISTEN_IMAGE_MC
- **说明**: 听录音，选择正确对应图片

#### 听音选择题
- **接口**: `POST /api/questions/choice/listen-sentence`
- **题型**: READ_SENTENCE_COMPREHENSION_CHOICE
- **说明**: 听录音，选择正确选项

#### 阅读选择题
- **接口**: `POST /api/questions/choice/read-sentence`
- **题型**: READ_SENTENCE_COMPREHENSION_CHOICE
- **说明**: 看文章，选择正确选项

### 配对题接口

#### 听音连图题
- **接口**: `POST /api/questions/match/listen-image`
- **题型**: LISTEN_IMAGE_MATCH
- **说明**: 听每条音频，与正确的图片进行配对

#### 读文连图题
- **接口**: `POST /api/questions/match/read-image`
- **题型**: READ_IMAGE_MATCH
- **说明**: 阅读文字，与正确的图片进行配对

#### 问答配对题
- **接口**: `POST /api/questions/match/read-dialog`
- **题型**: READ_DIALOGUE_MATCH
- **说明**: 将左侧问句与右侧恰当的回答进行配对

### 排序题接口

#### 连词成句题
- **接口**: `POST /api/questions/order/word`
- **题型**: READ_WORD_ORDER
- **说明**: 连词成句

## 支持的题目类型

### 听力类题目
1. **LISTEN_IMAGE_TRUE_FALSE** - 听录音，看图判断
   - 需要音频文件和图片
   - 判断题（正确/错误）
   - 技能类别：听力

2. **LISTEN_IMAGE_MC** - 听录音，看图选择
   - 需要音频文件和图片
   - 多选题
   - 技能类别：听力

3. **LISTEN_IMAGE_MATCH** - 听录音，看图配对
   - 需要音频文件和图片
   - 配对题
   - 技能类别：听力

4. **LISTEN_SENTENCE_QA** - 听录音，句子问答
   - 需要音频文件
   - 问答题
   - 技能类别：听力

5. **LISTEN_SENTENCE_TF** - 听录音，句子判断
   - 需要音频文件
   - 判断题
   - 技能类别：听力

### 阅读类题目
6. **READ_IMAGE_TRUE_FALSE** - 阅读，图片判断
   - 需要图片
   - 判断题
   - 技能类别：阅读

7. **READ_IMAGE_MATCH** - 阅读，看图配对
   - 需要图片
   - 配对题
   - 技能类别：阅读

8. **READ_DIALOGUE_MATCH** - 阅读，对话配对
   - 纯文本题目
   - 配对题
   - 技能类别：阅读

9. **READ_WORD_GAP_FILL** - 阅读，句子填空
   - 纯文本题目
   - 填空题
   - 技能类别：阅读

10. **READ_SENTENCE_COMPREHENSION_CHOICE** - 句子理解(选择)
    - 纯文本题目
    - 选择题
    - 技能类别：阅读

11. **READ_SENTENCE_TF** - 句子理解(判断)
    - 纯文本题目
    - 判断题
    - 技能类别：阅读

12. **READ_PARAGRAPH_COMPREHENSION** - 段落理解
    - 纯文本题目
    - 理解题
    - 技能类别：阅读

13. **READ_WORD_ORDER** - 连词成句
    - 纯文本题目
    - 排序题
    - 技能类别：阅读

### 翻译类题目
14. **READ_SENTENCE_TRANSLATION** - 句子翻译
    - 纯文本题目
    - 翻译题
    - 技能类别：翻译

## 数据结构说明

### SimpleQuestionContent结构
- `question`: 题目文本（字符串）
- `audioUrl`: 音频URL（可选，用于听力题目）
- `imageUrl`: 图片URL（可选，用于看图题目）
- `listeningText`: 听力文本内容（可选，音频对应的文字）

### SimpleQuestion结构
- `questionId`: 题目唯一标识（对应数据库exercise_id）
- `questionType`: 题目类型（如："LISTEN_IMAGE_TRUE_FALSE"）
- `content`: 题目内容（SimpleQuestionContent对象）
- `correctAnswer`: 正确答案（整数，1表示正确，0表示错误）

### 响应结构
- `count`: 实际返回的题目数量
- `sessionId`: 会话唯一标识（UUID格式）
- `questions`: 题目数组（SimpleQuestion对象列表）

## 使用示例

### Python示例

```python
import requests
import json

API_BASE = "http://localhost:8001/api/questions"

# 1. 获取支持的题目类型
def get_question_types():
    response = requests.get(f"{API_BASE}/types")
    return response.json()

# 2. 生成题目集合（新版通用接口）
def generate_exercise_collection():
    request_data = {
        "lessonId": "lesson_001",
        "duration": 1800,
        "exerciseTypes": ["LISTEN_IMAGE_TRUE_FALSE", "READ_SENTENCE_TF"],
        "token": "user_token_123",
        "count": 3,
        "phaseName": "初级",
        "topicName": "生活"
    }

    response = requests.post(f"{API_BASE}/generate", json=request_data)
    result = response.json()

    print(f"生成了 {result['count']} 道题目")
    print(f"会话ID: {result['sessionId']}")

    return result

# 3. 提交答案
def submit_answers(session_id, exercises):
    submission_list = []

    for exercise in exercises:
        # 根据题型构造不同的答案
        if exercise['exerciseType'] == 'LISTEN_IMAGE_TRUE_FALSE':
            user_answer = True  # 判断题答案
        elif 'CHOICE' in exercise['exerciseType']:
            user_answer = "A"   # 选择题答案
        elif 'MATCH' in exercise['exerciseType']:
            user_answer = {"0": "A", "1": "B"}  # 配对题答案
        elif 'ORDER' in exercise['exerciseType']:
            user_answer = ["1", "2", "3"]  # 排序题答案
        else:
            user_answer = True  # 默认判断题答案

        submission_list.append({
            "exerciseId": exercise['exerciseId'],
            "userAnswer": user_answer,
            "points": 3,
            "wrongAttempts": 0
        })

    submit_data = {
        "sessionId": session_id,
        "token": "user_token_123",
        "submission_list": submission_list
    }

    response = requests.post(f"{API_BASE}/submit", json=submit_data)
    return response.json()

# 4. 使用分类接口生成特定题型
def generate_specific_type():
    request_data = {
        "count": 2,
        "phaseName": "1A",
        "topicName": "学校生活"
    }

    # 生成听音看图判断题
    response = requests.post(f"{API_BASE}/tf/listen-image", json=request_data)
    tf_result = response.json()

    # 生成听音选图题
    response = requests.post(f"{API_BASE}/choice/listen-image", json=request_data)
    choice_result = response.json()

    # 生成听音连图题
    response = requests.post(f"{API_BASE}/match/listen-image", json=request_data)
    match_result = response.json()

    return tf_result, choice_result, match_result

# 5. 完整的学习流程示例
def complete_learning_workflow():
    # 步骤1: 获取题目类型
    types = get_question_types()
    print(f"系统支持 {len(types['questionTypes'])} 种题型")

    # 步骤2: 生成题目集合
    exercises_result = generate_exercise_collection()
    session_id = exercises_result['sessionId']
    exercises = exercises_result['exercises']

    # 步骤3: 显示题目信息
    for i, exercise in enumerate(exercises):
        print(f"\n题目 {i+1}:")
        print(f"  ID: {exercise['exerciseId']}")
        print(f"  类型: {exercise['exerciseType']}")
        print(f"  内容: {exercise['content']['prompt']}")
        if 'audioUrl' in exercise['content'] and exercise['content']['audioUrl']:
            print(f"  音频: {exercise['content']['audioUrl']}")
        if 'imageUrl' in exercise['content'] and exercise['content']['imageUrl']:
            print(f"  图片: {exercise['content']['imageUrl']}")

    # 步骤4: 提交答案
    submit_result = submit_answers(session_id, exercises)
    print(f"\n提交结果:")
    print(f"  总分: {submit_result['totalScore']}")
    print(f"  正确题数: {submit_result['correctCount']}/{submit_result['totalCount']}")

    # 步骤5: 查看详细结果
    for result in submit_result['results']:
        status = "正确" if result['isCorrect'] else "错误"
        print(f"  题目 {result['exerciseId']}: {status} (得分: {result['points']})")

# 执行示例
if __name__ == "__main__":
    print("=== 中文学习平台API使用示例 ===")
    complete_learning_workflow()

    print("\n=== 分类接口示例 ===")
    tf_result, choice_result, match_result = generate_specific_type()
    print(f"判断题: {tf_result['count']} 道")
    print(f"选择题: {choice_result['count']} 道")
    print(f"配对题: {match_result['count']} 道")
```

### JavaScript/Node.js示例

```javascript
const axios = require('axios');

const API_BASE = 'http://localhost:8001/api/questions';

// 1. 生成题目集合
async function generateExercises() {
    try {
        const requestData = {
            lessonId: "lesson_js_001",
            duration: 1800,
            exerciseTypes: ["LISTEN_IMAGE_TRUE_FALSE", "READ_SENTENCE_TF"],
            token: "js_token_001",
            count: 3,
            phaseName: "初级",
            topicName: "生活"
        };

        const response = await axios.post(`${API_BASE}/generate`, requestData);
        const result = response.data;

        console.log(`生成了 ${result.count} 道题目`);
        console.log(`会话ID: ${result.sessionId}`);

        return result;
    } catch (error) {
        console.error('生成题目失败:', error.message);
        throw error;
    }
}

// 2. 提交答案
async function submitAnswers(sessionId, exercises) {
    try {
        const submissionList = exercises.map(exercise => {
            let userAnswer;

            // 根据题型设置不同的答案格式
            switch (exercise.exerciseType) {
                case 'LISTEN_IMAGE_TRUE_FALSE':
                case 'READ_SENTENCE_TF':
                    userAnswer = true; // 判断题
                    break;
                case 'LISTEN_IMAGE_MC':
                    userAnswer = "A"; // 选择题
                    break;
                case 'LISTEN_IMAGE_MATCH':
                    userAnswer = {"0": "A", "1": "B"}; // 配对题
                    break;
                case 'READ_WORD_ORDER':
                    userAnswer = ["1", "2", "3"]; // 排序题
                    break;
                default:
                    userAnswer = true;
            }

            return {
                exerciseId: exercise.exerciseId,
                userAnswer: userAnswer,
                points: 3,
                wrongAttempts: 0
            };
        });

        const submitData = {
            sessionId: sessionId,
            token: "js_token_001",
            submission_list: submissionList
        };

        const response = await axios.post(`${API_BASE}/submit`, submitData);
        return response.data;

    } catch (error) {
        console.error('提交答案失败:', error.message);
        throw error;
    }
}

// 3. 使用分类接口
async function generateSpecificTypes() {
    const requestData = {
        count: 2,
        phaseName: "1A",
        topicName: "学校生活"
    };

    try {
        // 并行请求多种题型
        const [tfResult, choiceResult, matchResult] = await Promise.all([
            axios.post(`${API_BASE}/tf/listen-image`, requestData),
            axios.post(`${API_BASE}/choice/listen-image`, requestData),
            axios.post(`${API_BASE}/match/listen-image`, requestData)
        ]);

        return {
            tf: tfResult.data,
            choice: choiceResult.data,
            match: matchResult.data
        };
    } catch (error) {
        console.error('生成特定题型失败:', error.message);
        throw error;
    }
}

// 4. 完整的学习流程
async function completeLearningWorkflow() {
    try {
        console.log('=== 开始学习流程 ===');

        // 步骤1: 生成题目
        const exerciseResult = await generateExercises();
        const { sessionId, exercises } = exerciseResult;

        // 步骤2: 显示题目
        exercises.forEach((exercise, index) => {
            console.log(`\n题目 ${index + 1}:`);
            console.log(`  ID: ${exercise.exerciseId}`);
            console.log(`  类型: ${exercise.exerciseType}`);
            console.log(`  提示: ${exercise.content.prompt}`);

            if (exercise.content.audioUrl) {
                console.log(`  音频: ${exercise.content.audioUrl}`);
            }
            if (exercise.content.imageUrl) {
                console.log(`  图片: ${exercise.content.imageUrl}`);
            }
        });

        // 步骤3: 提交答案
        const submitResult = await submitAnswers(sessionId, exercises);

        console.log('\n=== 提交结果 ===');
        console.log(`总分: ${submitResult.totalScore}`);
        console.log(`正确率: ${submitResult.correctCount}/${submitResult.totalCount}`);

        // 步骤4: 显示详细结果
        submitResult.results.forEach(result => {
            const status = result.isCorrect ? '✓ 正确' : '✗ 错误';
            console.log(`题目 ${result.exerciseId}: ${status} (${result.points}分)`);
        });

    } catch (error) {
        console.error('学习流程出错:', error.message);
    }
}

// 5. 测试分类接口
async function testCategorizedAPIs() {
    try {
        console.log('\n=== 测试分类接口 ===');

        const results = await generateSpecificTypes();

        console.log(`判断题生成: ${results.tf.count} 道`);
        console.log(`选择题生成: ${results.choice.count} 道`);
        console.log(`配对题生成: ${results.match.count} 道`);

    } catch (error) {
        console.error('分类接口测试失败:', error.message);
    }
}

// 执行示例
async function runExamples() {
    await completeLearningWorkflow();
    await testCategorizedAPIs();
}

// 启动示例
runExamples().catch(console.error);
```

## 项目结构

```
src/app/
├── question/                    # 题目模块（新重构）
│   ├── __init__.py             # 模块初始化
│   ├── schemas.py              # 数据模型定义
│   ├── service.py              # 业务逻辑层
│   └── router.py               # API路由层
├── routers/                    # 其他路由模块
├── main.py                     # 应用入口
└── database.py                 # 数据库配置
```

## 启动服务

```bash
# 方法1：直接启动
cd /mnt/data/chinese_platform_backend
python -c "import sys; sys.path.append('src'); from app.main import app; import uvicorn; uvicorn.run(app, host='0.0.0.0', port=8001)"

# 方法2：使用uvicorn命令
cd src
uvicorn app.main:app --host 0.0.0.0 --port 8001 --reload
```

服务启动后访问:
- **API文档**: http://localhost:8001/docs
- **题目类型接口**: http://localhost:8001/api/questions/types
- **生成题目集合**: http://localhost:8001/api/questions/generate
- **提交答案**: http://localhost:8001/api/questions/submit

## 完整的API接口列表

### 核心接口
- `POST /api/questions/generate` - 生成题目集合（主要接口）
- `POST /api/questions/submit` - 提交答案
- `GET /api/questions/types` - 获取题目类型

### 兼容接口
- `POST /api/questions/listen-image-true-false` - 听录音看图判断题（兼容）

### 判断题接口
- `POST /api/questions/tf/listen-image` - 听音看图判断题
- `POST /api/questions/tf/read-image` - 读词看图判断题
- `POST /api/questions/tf/listen-sentence` - 听音看句判断题
- `POST /api/questions/tf/read-sentence` - 阅读判断题

### 选择题接口
- `POST /api/questions/choice/listen-image` - 听音选图题
- `POST /api/questions/choice/listen-sentence` - 听音选择题
- `POST /api/questions/choice/read-sentence` - 阅读选择题

### 配对题接口
- `POST /api/questions/match/listen-image` - 听音连图题
- `POST /api/questions/match/read-image` - 读文连图题
- `POST /api/questions/match/read-dialog` - 问答配对题

### 排序题接口
- `POST /api/questions/order/word` - 连词成句题

## 答案格式说明

根据题目设计文档，不同题型的答案格式如下：

### 判断题 (TF)
```json
{
  "userAnswer": true,  // true表示正确，false表示错误
  "correctAnswer": true
}
```

### 选择题 (Choice)
```json
{
  "userAnswer": "A",  // 选项标签
  "correctAnswer": "A"
}
```

### 配对题 (Match)
```json
{
  "userAnswer": {"0": "A", "1": "B"},  // 左侧项目与右侧项目的配对关系
  "correctAnswer": {"0": "A", "1": "B"}
}
```

### 排序题 (Order)
```json
{
  "userAnswer": ["1", "2", "3"],  // 正确的排序
  "correctAnswer": ["1", "2", "3"]
}
```

## 注意事项

1. **数据库连接**: 确保PostgreSQL数据库正常运行并且连接配置正确
2. **媒体文件**: 音频和图片文件需要配置正确的访问路径
3. **筛选参数**: phaseName、topicName、lessonName必须与数据库中的实际数据匹配
4. **答案格式**: 提交答案时必须使用正确的数据类型（布尔值、字符串、数组、对象）
5. **会话管理**: 每次生成题目都会产生唯一的sessionId，提交答案时必须使用对应的sessionId
6. **错误处理**: API会返回详细的错误信息，便于调试
7. **题型支持**: 系统支持14种不同的题型，涵盖听力、阅读、翻译三大技能类别
8. **批量操作**: 支持一次生成多道不同类型的题目，也支持批量提交多个答案

## 版本兼容性

- **新版接口**: 使用 `/api/questions/generate` 和 `/api/questions/submit` 获得完整功能
- **旧版接口**: `/api/questions/listen-image-true-false` 保持兼容，用于特定需求
- **分类接口**: 按题型分类的接口便于前端按需调用特定类型的题目

## 性能优化建议

1. **缓存策略**: 题目类型信息可以缓存，减少重复请求
2. **批量处理**: 优先使用通用生成接口批量获取多种题型
3. **并发请求**: JavaScript示例中展示了如何并行请求多种题型
4. **会话复用**: 同一学习会话中的多次提交可以使用相同的sessionId追踪