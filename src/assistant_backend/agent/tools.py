import json
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from assistant_backend.application.tasks import TaskFailure, TaskService


class SearchTaskArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")

    keyword: str | None = Field(default=None, max_length=200)
    due_from: date | None = None
    due_to: date | None = None
    important: bool | None = None
    urgent: bool | None = None
    status: Literal["open", "completed"] | None = None
    category: str | None = Field(default=None, max_length=64)
    limit: int = Field(default=20, ge=1, le=20)


class GetTaskArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str = Field(min_length=1, max_length=36)


TASK_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_tasks",
            "description": "Read tasks belonging to the authenticated user, with optional filters.",
            "strict": True,
            "parameters": {
                "type": "object",
                "properties": {
                    "keyword": {"type": ["string", "null"], "maxLength": 200},
                    "due_from": {"type": ["string", "null"], "format": "date"},
                    "due_to": {"type": ["string", "null"], "format": "date"},
                    "important": {"type": ["boolean", "null"]},
                    "urgent": {"type": ["boolean", "null"]},
                    "status": {"type": ["string", "null"], "enum": ["open", "completed", None]},
                    "category": {"type": ["string", "null"], "maxLength": 64},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 20},
                },
                "required": [
                    "keyword",
                    "due_from",
                    "due_to",
                    "important",
                    "urgent",
                    "status",
                    "category",
                    "limit",
                ],
                "additionalProperties": False,
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_task",
            "description": "Read one task owned by the authenticated user.",
            "strict": True,
            "parameters": {
                "type": "object",
                "properties": {"task_id": {"type": "string", "minLength": 1, "maxLength": 36}},
                "required": ["task_id"],
                "additionalProperties": False,
            },
        },
    },
]


class ReadOnlyTaskTools:
    def __init__(self, service: TaskService, user_id: str) -> None:
        self.service = service
        self.user_id = user_id

    def invoke(self, name: str, raw_arguments: str) -> str:
        try:
            if name == "search_tasks":
                args = SearchTaskArguments.model_validate_json(raw_arguments)
                result = self.service.list(
                    self.user_id,
                    keyword=args.keyword,
                    due_from=args.due_from,
                    due_to=args.due_to,
                    important=args.important,
                    urgent=args.urgent,
                    status=args.status,
                    category=args.category,
                    limit=args.limit,
                )
                return json.dumps(result.model_dump(mode="json"), ensure_ascii=False)
            if name == "get_task":
                args = GetTaskArguments.model_validate_json(raw_arguments)
                result = self.service.get(self.user_id, args.task_id)
                return json.dumps(result.model_dump(mode="json"), ensure_ascii=False)
            return json.dumps({"error": "unknown_tool"})
        except ValidationError:
            return json.dumps({"error": "invalid_arguments"})
        except TaskFailure as exc:
            return json.dumps({"error": exc.code.lower()})
