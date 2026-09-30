from typing import Any
import storage.wordbook_store as store
from agent.tools.base import Tool
import asyncio

class StudentStatTool(Tool):
    @property
    def name(self) -> str:
        return "get_student_stat"

    @property
    def description(self) -> str:
        return "查一个学生的学习统计（新词数、学习中、到期、已掌握、总复习次数）。用户问学习进度时用它。"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties":{
                "student_id":{"type":"integer", "description":"学生 ID"}
            },
            "required":["student_id"],
        }
    async def execute(self,student_id: int) -> dict:
        return await asyncio.to_thread(store.get_student_stat, student_id)
    
class ImportWordTool(Tool):
    def __init__(self, embedder):
        self.embedder = embedder

    @property
    def name(self) -> str:
        return "import_word"

    @property
    def description(self) -> str:
        return "把一个新单词导入词库（中文 cn_text、韩语 kor_text、可选的补充说明 extra_info、词库标签 library_tag）。当用户要添加新词时用它。"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type":"object",
            "properties":{
                "cn_text":{"type":"string", "description":"单词的中文"},
                "kor_text":{"type":"string", "description":"导入单词的韩文"},
                "extra_info":{"type":"string", "description":"导入单词的补充说明"},
                "library_tag":{"type":"string", "description":"词库标签"},
            },
            "required":["cn_text", "kor_text", "library_tag"]
        }
    async def execute(self,cn_text: str, kor_text: str, library_tag: str, extra_info: str | None=None) -> dict:
            vector = await self.embedder.embed(f"{cn_text} {kor_text}")
            if not vector:
                vector = None
            n = await asyncio.to_thread(store.import_word_library, cn_text, kor_text, extra_info, library_tag, vector)
            return {"imported": n}

class GetReviewBatchTool(Tool):
    @property
    def name(self) -> str:
        return "get_review_batch"

    @property
    def description(self) -> str:
        return "获取一批复习任务，优先到期复习词，再补充指定数量新词，标记类型为 review/new"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties":{
                "student_id":{"type":"integer", "description": "学生ID"},
                "new_limit":{"type":"integer", "description": "新学单词的数量"},
                "due_limit":{"type":"integer", "description": "复习单词的数量"},
                },
            "required":["student_id"],
        }
    async def execute(self, student_id:int, new_limit = 5, due_limit = 10) -> list[dict]:
        return await asyncio.to_thread(store.get_review_batch, student_id, new_limit, due_limit)

class FetchQuizOptionsTool(Tool):
    @property
    def name(self) -> str:
        return "fetch_quiz_options"

    @property
    def description(self) -> str:
        return "获取目标单词的正确选项 + 随机错误选项，用于生成选择题。"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties":{
                "word_id":{"type":"integer", "description": "单词ID"},
                "count":{"type":"integer", "description": "选项数量"},
            },
            "required":["word_id"],
        }
    async def execute(self, word_id: int, count: int = 3) -> list[dict]:
        return await asyncio.to_thread(store.fetch_quiz_options, word_id, count)

class RecordAnswerTool(Tool):
    @property
    def name(self) -> str:
        return "record_answer"

    @property
    def description(self) -> str:
        return "记录学生单词作答结果，调用 SRS 算法更新复习间隔与熟练度，处理版本冲突校验。"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties":{
                "student_id":{"type":"integer", "description": "学生ID"},
                "word_id":{"type":"integer", "description": "单词ID"},
                "is_correct":{"type":"boolean", "description": "正确与否"},
                "word_version": {"type": "integer", "description": "单词版本（从批次里取）"},
            },
            "required":["student_id", "word_id", "is_correct", "word_version"],
        }
    async def execute(self, student_id:int, word_id:int, is_correct:bool, word_version:int) -> dict:
        return await asyncio.to_thread(store.record_answer, student_id, word_id, is_correct, word_version)

class GetStudentInfoTool(Tool):
    @property
    def name(self) -> str:
        return "get_student_info"

    @property
    def description(self) -> str:
        return "查询学生的基本信息(学号、姓名、分班)"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties":{
                "student_id":{"type":"integer", "description": "学生ID"},
            },
            "required":["student_id"],
        }
    async def execute(self, student_id: int) -> dict|None:
        return await asyncio.to_thread(store.get_student, student_id)

class ListStudentsTool(Tool):
    @property
    def name(self) -> str:
        return "list_students"

    @property
    def description(self) -> str:
        return "查询学生列表，按 student_id 升序返回学生 ID、姓名、班级名称。"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type":"object",
            "properties":{},
        }
    async def execute(self) -> list[dict]:
        return await asyncio.to_thread(store.list_students)

class DeleteWordTool(Tool):
    @property
    def name(self) -> str:
        return "delete_word"

    @property
    def description(self) ->str:
        return "软删除一个单词（is_deleted 置真）。用户说「删掉这个词」时用它。"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties":{
                "word_id":{"type":"integer", "description": "要删除的单词ID"},
            }
        }
    async def execute(self, word_id) -> dict:
        return await asyncio.to_thread(store.delete_word, word_id)

class UpdateWordTool(Tool):
    @property
    def name(self) -> str:
        return "update_word"

    @property
    def description(self) -> str:
        return "修改一个单词的中文、韩文、补充说明。改完该词 embedding 会置空，由 backfill 重新生成。"

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties":{
                "word_id":{"type":"integer", "description": "要修改的单词ID"},
                "cn_text":{"type":"string", "description":"新的中文"},
                "kor_text":{"type":"string", "description":"新的单词的韩文"},
                "extra_info":{"type":"string", "description":"新的补充说明"},
            }
        }
    async def execute(self, word_id: int, cn_text: str, kor_text: str, extra_info: str) -> dict:
        return await asyncio.to_thread(store.update_word, word_id, cn_text, kor_text, extra_info)