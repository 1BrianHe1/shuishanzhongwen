# 中文学习平台API测试命令集合

## 服务启动命令

```bash
# 启动服务器
cd /mnt/data/chinese_platform_backend
python -c "import sys; sys.path.append('src'); from app.main import app; import uvicorn; uvicorn.run(app, host='0.0.0.0', port=8002)"
```

## 核心接口测试

### 1. 获取题目类型
```bash
curl "http://localhost:8002/api/questions/types"
```

### 2. 生成题目集合（通用接口）
```bash
# 基础测试
curl -X POST "http://localhost:8002/api/questions/generate" \
  -H "Content-Type: application/json" \
  -d '{"count": 1, "exerciseTypes": ["LISTEN_IMAGE_TRUE_FALSE"]}'

# 完整参数测试
curl -X POST "http://localhost:8002/api/questions/generate" \
  -H "Content-Type: application/json" \
  -d '{
    "lessonId": "lesson_001",
    "duration": 1800,
    "exerciseTypes": ["LISTEN_IMAGE_TRUE_FALSE", "READ_SENTENCE_TF"],
    "token": "user_token_123",
    "count": 3,
    "phaseName": "1A",
    "topicName": "学校生活",
    "lessonName": "我的班级"
  }'

# 混合题型测试
curl -X POST "http://localhost:8002/api/questions/generate" \
  -H "Content-Type: application/json" \
  -d '{
    "exerciseTypes": ["LISTEN_IMAGE_TRUE_FALSE", "READ_IMAGE_TRUE_FALSE", "LISTEN_IMAGE_MC"],
    "count": 3
  }'
```

### 3. 提交答案
```bash
# 提交判断题答案
curl -X POST "http://localhost:8002/api/questions/submit" \
  -H "Content-Type: application/json" \
  -d '{
    "sessionId": "12f6a89e-afcb-4536-b555-06a33f503c5f",
    "token": "user_token_123",
    "submission_list": [
      {
        "exerciseId": "1fe2d43b-0fae-49ba-8650-8f8321e7604f",
        "userAnswer": true,
        "points": 3,
        "wrongAttempts": 0
      }
    ]
  }'

# 提交多种题型答案
curl -X POST "http://localhost:8002/api/questions/submit" \
  -H "Content-Type: application/json" \
  -d '{
    "sessionId": "session_123",
    "submission_list": [
      {"exerciseId": "q1", "userAnswer": true, "points": 3},
      {"exerciseId": "q2", "userAnswer": "A", "points": 5},
      {"exerciseId": "q3", "userAnswer": {"0": "A", "1": "B"}, "points": 4},
      {"exerciseId": "q4", "userAnswer": ["1", "2", "3"], "points": 6}
    ]
  }'
```

## 兼容接口测试

### 听录音看图判断题（旧版兼容）
```bash
# 基础测试
curl -X POST "http://localhost:8002/api/questions/listen-image-true-false" \
  -H "Content-Type: application/json" \
  -d '{"count": 1, "userId": "test_user", "token": "test_token"}'

# 带筛选条件
curl -X POST "http://localhost:8002/api/questions/listen-image-true-false" \
  -H "Content-Type: application/json" \
  -d '{
    "count": 2,
    "userId": "test_user",
    "token": "test_token",
    "phaseName": "1A",
    "topicName": "学校生活",
    "lessonName": "我的班级"
  }'
```

## 判断题接口测试

### 1. 听音看图判断题
```bash
curl -X POST "http://localhost:8002/api/questions/tf/listen-image" \
  -H "Content-Type: application/json" \
  -d '{"count": 1, "phaseName": "1A"}'
```

### 2. 读词看图判断题
```bash
curl -X POST "http://localhost:8002/api/questions/tf/read-image" \
  -H "Content-Type: application/json" \
  -d '{"count": 1}'
```

### 3. 听音看句判断题
```bash
curl -X POST "http://localhost:8002/api/questions/tf/listen-sentence" \
  -H "Content-Type: application/json" \
  -d '{"count": 1, "topicName": "生活"}'
```

### 4. 阅读判断题
```bash
curl -X POST "http://localhost:8002/api/questions/tf/read-sentence" \
  -H "Content-Type: application/json" \
  -d '{"count": 1}'
```

## 选择题接口测试

### 1. 听音选图题
```bash
curl -X POST "http://localhost:8002/api/questions/choice/listen-image" \
  -H "Content-Type: application/json" \
  -d '{"count": 1}'
```

### 2. 听音选择题
```bash
curl -X POST "http://localhost:8002/api/questions/choice/listen-sentence" \
  -H "Content-Type: application/json" \
  -d '{"count": 1, "phaseName": "初级"}'
```

### 3. 阅读选择题
```bash
curl -X POST "http://localhost:8002/api/questions/choice/read-sentence" \
  -H "Content-Type: application/json" \
  -d '{"count": 1}'
```

## 配对题接口测试

### 1. 听音连图题
```bash
curl -X POST "http://localhost:8002/api/questions/match/listen-image" \
  -H "Content-Type: application/json" \
  -d '{"count": 1}'
```

### 2. 读文连图题
```bash
curl -X POST "http://localhost:8002/api/questions/match/read-image" \
  -H "Content-Type: application/json" \
  -d '{"count": 1, "topicName": "职业"}'
```

### 3. 问答配对题
```bash
curl -X POST "http://localhost:8002/api/questions/match/read-dialog" \
  -H "Content-Type: application/json" \
  -d '{"count": 1}'
```

## 排序题接口测试

### 连词成句题
```bash
curl -X POST "http://localhost:8002/api/questions/order/word" \
  -H "Content-Type: application/json" \
  -d '{"count": 1}'
```

## 批量测试脚本

### 测试所有判断题接口
```bash
#!/bin/bash
echo "=== 测试所有判断题接口 ==="
echo "1. 听音看图判断题:"
curl -X POST "http://localhost:8002/api/questions/tf/listen-image" -H "Content-Type: application/json" -d '{"count": 1}' | jq .

echo -e "\n2. 读词看图判断题:"
curl -X POST "http://localhost:8002/api/questions/tf/read-image" -H "Content-Type: application/json" -d '{"count": 1}' | jq .

echo -e "\n3. 听音看句判断题:"
curl -X POST "http://localhost:8002/api/questions/tf/listen-sentence" -H "Content-Type: application/json" -d '{"count": 1}' | jq .

echo -e "\n4. 阅读判断题:"
curl -X POST "http://localhost:8002/api/questions/tf/read-sentence" -H "Content-Type: application/json" -d '{"count": 1}' | jq .
```

### 测试所有选择题接口
```bash
#!/bin/bash
echo "=== 测试所有选择题接口 ==="
echo "1. 听音选图题:"
curl -X POST "http://localhost:8002/api/questions/choice/listen-image" -H "Content-Type: application/json" -d '{"count": 1}' | jq .

echo -e "\n2. 听音选择题:"
curl -X POST "http://localhost:8002/api/questions/choice/listen-sentence" -H "Content-Type: application/json" -d '{"count": 1}' | jq .

echo -e "\n3. 阅读选择题:"
curl -X POST "http://localhost:8002/api/questions/choice/read-sentence" -H "Content-Type: application/json" -d '{"count": 1}' | jq .
```

### 测试所有配对题接口
```bash
#!/bin/bash
echo "=== 测试所有配对题接口 ==="
echo "1. 听音连图题:"
curl -X POST "http://localhost:8002/api/questions/match/listen-image" -H "Content-Type: application/json" -d '{"count": 1}' | jq .

echo -e "\n2. 读文连图题:"
curl -X POST "http://localhost:8002/api/questions/match/read-image" -H "Content-Type: application/json" -d '{"count": 1}' | jq .

echo -e "\n3. 问答配对题:"
curl -X POST "http://localhost:8002/api/questions/match/read-dialog" -H "Content-Type: application/json" -d '{"count": 1}' | jq .
```

## 完整学习流程测试

### 1. 生成题目 -> 2. 提交答案 -> 3. 查看结果
```bash
#!/bin/bash
echo "=== 完整学习流程测试 ==="

# 步骤1: 生成题目
echo "1. 生成题目..."
RESPONSE=$(curl -s -X POST "http://localhost:8002/api/questions/generate" \
  -H "Content-Type: application/json" \
  -d '{"exerciseTypes": ["LISTEN_IMAGE_TRUE_FALSE"], "count": 2}')

echo "$RESPONSE" | jq .

# 提取sessionId和exerciseId
SESSION_ID=$(echo "$RESPONSE" | jq -r '.sessionId')
EXERCISE_ID=$(echo "$RESPONSE" | jq -r '.exercises[0].exerciseId')

echo -e "\n2. 提交答案..."
# 步骤2: 提交答案
curl -s -X POST "http://localhost:8002/api/questions/submit" \
  -H "Content-Type: application/json" \
  -d "{
    \"sessionId\": \"$SESSION_ID\",
    \"submission_list\": [
      {\"exerciseId\": \"$EXERCISE_ID\", \"userAnswer\": true, \"points\": 3}
    ]
  }" | jq .
```

## 性能测试

### 并发请求测试
```bash
#!/bin/bash
echo "=== 并发请求测试 ==="
for i in {1..5}; do
  curl -X POST "http://localhost:8002/api/questions/generate" \
    -H "Content-Type: application/json" \
    -d '{"count": 1}' &
done
wait
echo "并发测试完成"
```

### 大批量题目生成测试
```bash
curl -X POST "http://localhost:8002/api/questions/generate" \
  -H "Content-Type: application/json" \
  -d '{
    "exerciseTypes": [
      "LISTEN_IMAGE_TRUE_FALSE",
      "READ_IMAGE_TRUE_FALSE",
      "LISTEN_IMAGE_MC",
      "READ_SENTENCE_TF"
    ],
    "count": 10
  }'
```

## 错误测试

### 无效参数测试
```bash
# 测试无效的exerciseType
curl -X POST "http://localhost:8002/api/questions/generate" \
  -H "Content-Type: application/json" \
  -d '{"exerciseTypes": ["INVALID_TYPE"], "count": 1}'

# 测试无效的sessionId
curl -X POST "http://localhost:8002/api/questions/submit" \
  -H "Content-Type: application/json" \
  -d '{
    "sessionId": "invalid_session",
    "submission_list": [{"exerciseId": "test", "userAnswer": true}]
  }'
```

## 使用说明

1. **替换端口**: 根据实际服务器端口修改URL中的端口号
2. **格式化输出**: 可以在curl命令后添加 `| jq .` 来格式化JSON输出
3. **保存响应**: 使用 `-o filename.json` 保存响应到文件
4. **详细信息**: 添加 `-v` 参数查看详细的请求/响应信息
5. **静默模式**: 添加 `-s` 参数隐藏进度信息

## 常用组合命令

```bash
# 格式化输出
curl -s "http://localhost:8002/api/questions/types" | python -m json.tool

# 保存响应
curl -s -X POST "http://localhost:8002/api/questions/generate" \
  -H "Content-Type: application/json" \
  -d '{"count": 5}' \
  -o generated_questions.json

# 只查看HTTP状态码
curl -s -o /dev/null -w "%{http_code}" "http://localhost:8002/api/questions/types"

# 计时测试
curl -s -w "总时间: %{time_total}s\n" \
  -X POST "http://localhost:8002/api/questions/generate" \
  -H "Content-Type: application/json" \
  -d '{"count": 1}' \
  -o /dev/null
```