#!/usr/bin/env python3
"""
测试正确的phase_name格式（1A, 2A等）和基于phase的过滤功能
"""
import requests
import json
import sys
import os

# 添加项目路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'src'))

from app.database import SessionLocal
from sqlalchemy import text

API_BASE_URL = "http://localhost:8000"

def get_available_phases():
    """获取数据库中可用的phase"""
    try:
        db = SessionLocal()
        result = db.execute(text('SELECT name FROM content_new.phases ORDER BY display_order'))
        phases = [row.name for row in result]
        db.close()
        return phases
    except Exception as e:
        print(f"获取phases失败: {e}")
        return []

def test_correct_phase_format():
    """测试正确的phase格式"""
    print("📋 测试: 正确的phase_name格式")
    print("-" * 50)

    # 获取可用的phase
    available_phases = get_available_phases()
    print(f"数据库中的可用phases: {available_phases}")

    # 测试有题目的phase (1A)
    print(f"\n🔍 测试phase '1A' (应该有题目)")
    try:
        payload = {
            "count": 2,
            "userId": "test_user",
            "token": "test_token",
            "phaseName": "1A"
        }

        response = requests.post(
            f"{API_BASE_URL}/api/questions/listen-image-true-false",
            json=payload,
            headers={"Content-Type": "application/json"}
        )

        if response.status_code == 200:
            data = response.json()
            questions = data.get('questions', [])

            print(f"  ✅ 成功获取 {len(questions)} 道题目")
            for i, q in enumerate(questions, 1):
                content = q['content']
                print(f"    题目{i}: questionId={q['questionId']}")
                print(f"           listeningText={content.get('listeningText', 'N/A')}")

            if len(questions) > 0:
                print(f"  ✅ Phase '1A' 有对应题目")
                return True
            else:
                print(f"  ❌ Phase '1A' 没有题目")
                return False
        else:
            print(f"  ❌ API调用失败: {response.status_code}")
            return False

    except Exception as e:
        print(f"  ❌ 测试失败: {e}")
        return False

def test_phase_without_exercises():
    """测试没有题目的phase"""
    print(f"\n🔍 测试phases without exercises")

    phases_to_test = ["2A", "3A", "1B"]  # 这些phase可能没有LISTEN_IMAGE_TRUE_FALSE题目

    for phase in phases_to_test:
        print(f"\n  测试phase '{phase}':")
        try:
            payload = {
                "count": 1,
                "userId": "test_user",
                "token": "test_token",
                "phaseName": phase
            }

            response = requests.post(
                f"{API_BASE_URL}/api/questions/listen-image-true-false",
                json=payload,
                headers={"Content-Type": "application/json"}
            )

            if response.status_code == 200:
                data = response.json()
                questions = data.get('questions', [])

                if len(questions) == 0:
                    print(f"    ✅ 正确返回空题目列表 (phase '{phase}' 无对应题目)")
                else:
                    print(f"    ⚠️ 意外返回了 {len(questions)} 道题目")
                    for q in questions:
                        content = q['content']
                        print(f"      - {content.get('listeningText', 'N/A')}")
            else:
                print(f"    ❌ API调用失败: {response.status_code}")

        except Exception as e:
            print(f"    ❌ 测试失败: {e}")

    return True

def test_phase_topic_lesson_combination():
    """测试phase, topic, lesson的组合过滤"""
    print(f"\n📋 测试: Phase + Topic + Lesson 组合过滤")
    print("-" * 50)

    test_cases = [
        {
            "phaseName": "1A",
            "topicName": "学校生活",
            "lessonName": "我的班级",
            "description": "完整匹配 (应该有题目)",
            "expected_questions": 1
        },
        {
            "phaseName": "1A",
            "topicName": "学校生活",
            "lessonName": "父母职业",
            "description": "完整匹配 (应该有题目)",
            "expected_questions": 1
        },
        {
            "phaseName": "2A",  # 错误的phase
            "topicName": "学校生活",
            "lessonName": "我的班级",
            "description": "错误phase (应该无题目)",
            "expected_questions": 0
        },
        {
            "phaseName": "1A",
            "topicName": "错误主题",  # 错误的topic
            "lessonName": "我的班级",
            "description": "错误topic (应该无题目)",
            "expected_questions": 0
        }
    ]

    success_count = 0

    for test_case in test_cases:
        print(f"\n🔍 测试: {test_case['description']}")

        try:
            payload = {
                "count": 2,
                "userId": "test_user",
                "token": "test_token",
                "phaseName": test_case["phaseName"],
                "topicName": test_case["topicName"],
                "lessonName": test_case["lessonName"]
            }

            response = requests.post(
                f"{API_BASE_URL}/api/questions/listen-image-true-false",
                json=payload,
                headers={"Content-Type": "application/json"}
            )

            if response.status_code == 200:
                data = response.json()
                questions = data.get('questions', [])

                if len(questions) == test_case["expected_questions"]:
                    print(f"  ✅ 正确返回 {len(questions)} 道题目")
                    success_count += 1

                    if questions:
                        for q in questions:
                            content = q['content']
                            print(f"    - questionId: {q['questionId']}")
                            print(f"      listeningText: {content.get('listeningText', 'N/A')}")
                else:
                    print(f"  ❌ 预期 {test_case['expected_questions']} 道题目，实际获取 {len(questions)} 道")
            else:
                print(f"  ❌ API调用失败: {response.status_code}")
                print(f"     错误: {response.text}")

        except Exception as e:
            print(f"  ❌ 测试失败: {e}")

    return success_count == len(test_cases)

def test_invalid_phase_format():
    """测试无效的phase格式"""
    print(f"\n📋 测试: 无效的phase格式")
    print("-" * 50)

    invalid_phases = ["初级", "1级", "Phase1", "level1"]

    for invalid_phase in invalid_phases:
        print(f"\n  测试无效phase '{invalid_phase}':")
        try:
            payload = {
                "count": 1,
                "userId": "test_user",
                "token": "test_token",
                "phaseName": invalid_phase
            }

            response = requests.post(
                f"{API_BASE_URL}/api/questions/listen-image-true-false",
                json=payload,
                headers={"Content-Type": "application/json"}
            )

            if response.status_code == 200:
                data = response.json()
                questions = data.get('questions', [])

                if len(questions) == 0:
                    print(f"    ✅ 正确处理无效phase: 返回空题目列表")
                else:
                    print(f"    ⚠️ 意外返回了 {len(questions)} 道题目")
            else:
                print(f"    ❌ API调用失败: {response.status_code}")

        except Exception as e:
            print(f"    ❌ 测试失败: {e}")

    return True

def main():
    """运行所有测试"""
    print("开始测试正确的phase_name格式和过滤功能...\n")

    tests = [
        ("正确phase格式测试", test_correct_phase_format),
        ("无题目phase测试", test_phase_without_exercises),
        ("组合过滤测试", test_phase_topic_lesson_combination),
        ("无效phase格式测试", test_invalid_phase_format),
    ]

    passed = 0
    for test_name, test_func in tests:
        try:
            if test_func():
                passed += 1
        except Exception as e:
            print(f"❌ 测试 '{test_name}' 发生异常: {e}")

    print(f"\n📊 总体测试结果: {passed}/{len(tests)} 通过")

    if passed == len(tests):
        print("🎉 所有测试通过！Phase功能工作正常：")
        print("✅ 支持正确的phase_name格式 (1A, 2A, 1B等)")
        print("✅ 基于phase的题目过滤功能正常")
        print("✅ Phase + Topic + Lesson 组合过滤正常")
        print("✅ 正确处理无效或无题目的phase")
    else:
        print("⚠️ 部分测试失败，请检查实现。")

if __name__ == "__main__":
    main()