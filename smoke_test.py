from storage import wordbook_store as store

sid = store.add_student("测试学生", "测试班")
test_stat = store.get_student_stat(sid)
print(f"测试学生id：{sid}")
print(f"测试学生状态d：{test_stat}")