from unittest import TestCase
from unittest.mock import patch

from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.ai.llm_client import LlmCompletionRequest, LlmProviderError, complete_text
from app.database.session import Base
from app.models.user import User
from app.repositories.llm_key_repository import create_llm_key, decrypt_llm_key, update_llm_key
from app.schemas.llm_key import LlmKeyCreate, LlmKeyUpdate, LlmProvider


class LlmKeyRepositoryTests(TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)
        self.user = User(email="raj@example.com", full_name="Raj", hashed_password="hashed")
        self.db.add(self.user)
        self.db.commit()
        self.db.refresh(self.user)

    def tearDown(self) -> None:
        self.db.close()
        self.engine.dispose()

    def test_key_is_encrypted_and_masked(self) -> None:
        record = create_llm_key(
            self.db,
            self.user,
            LlmKeyCreate(provider=LlmProvider.GROQ, api_key="gsk_test_1234567890"),
        )

        self.assertNotIn("gsk_test", record.encrypted_api_key)
        self.assertEqual("gsk_...7890", record.key_preview)
        self.assertEqual("qwen/qwen3-32b", record.default_model)
        self.assertEqual("gsk_test_1234567890", decrypt_llm_key(record))

    def test_update_replaces_encrypted_key(self) -> None:
        record = create_llm_key(
            self.db,
            self.user,
            LlmKeyCreate(provider=LlmProvider.OPENAI, api_key="sk_old_1234567890"),
        )
        updated = update_llm_key(
            self.db,
            record,
            LlmKeyUpdate(api_key="sk_new_abcdefghij", label="OpenAI Personal", is_active=False),
        )

        self.assertEqual("OpenAI Personal", updated.label)
        self.assertFalse(updated.is_active)
        self.assertEqual("sk_new_abcdefghij", decrypt_llm_key(updated))

    def test_rejects_swagger_placeholder_as_model_name(self) -> None:
        with self.assertRaises(ValidationError):
            LlmKeyCreate(
                provider=LlmProvider.OPENAI,
                api_key="sk_test_1234567890",
                default_model="string",
            )

    def test_provider_guard_rejects_placeholder_model_without_network_call(self) -> None:
        with self.assertRaisesRegex(LlmProviderError, "Invalid model configuration"):
            complete_text(
                LlmCompletionRequest(
                    provider=LlmProvider.OPENAI,
                    api_key="sk_test_1234567890",
                    model="string",
                    system_prompt="test",
                    user_prompt="test",
                )
            )
