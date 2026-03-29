"""
Tests for NeuroMem Inngest workflow module.

Tests the workflow module components that work without
the Inngest server running (client, events, config).
"""

import pytest
import uuid


class TestWorkflowImports:
    """Test that workflow module imports work gracefully."""

    def test_client_import(self):
        """Test client module imports without inngest installed."""
        from neuromem.workflows.client import INNGEST_AVAILABLE

        # Should be False if inngest not installed, True if installed
        assert isinstance(INNGEST_AVAILABLE, bool)

    def test_events_import(self):
        """Test events module imports."""
        from neuromem.workflows.events import NeuroMemEvents

        assert hasattr(NeuroMemEvents, "MEMORY_OBSERVED")
        assert hasattr(NeuroMemEvents, "CONSOLIDATION_REQUESTED")
        assert hasattr(NeuroMemEvents, "MAINTENANCE_FULL_CYCLE")
        assert hasattr(NeuroMemEvents, "MEMORY_BATCH_INGEST")

    def test_event_names_format(self):
        """Test that event names follow the neuromem/ prefix convention."""
        from neuromem.workflows.events import NeuroMemEvents

        event_attrs = [
            a
            for a in dir(NeuroMemEvents)
            if not a.startswith("_") and isinstance(getattr(NeuroMemEvents, a), str)
        ]

        for attr in event_attrs:
            value = getattr(NeuroMemEvents, attr)
            assert value.startswith(
                "neuromem/"
            ), f"Event {attr} = '{value}' must start with 'neuromem/'"

    def test_workflows_init_import(self):
        """Test top-level workflows package import."""
        from neuromem.workflows import (
            get_inngest_client,
            create_neuromem_workflows,
            create_workflow_app,
        )

        assert callable(get_inngest_client)
        assert callable(create_neuromem_workflows)
        assert callable(create_workflow_app)


class TestWorkflowConfig:
    """Test workflow configuration."""

    def test_config_workflows_accessor(self):
        """Test NeuroMemConfig.workflows() returns expected structure."""
        from neuromem.config import NeuroMemConfig

        config = NeuroMemConfig("neuromem.yaml")
        wf = config.workflows()

        assert isinstance(wf, dict)
        assert "enabled" in wf
        assert "cron" in wf
        assert "app_id" in wf

    def test_config_cron_schedules(self):
        """Test cron schedule configuration."""
        from neuromem.config import NeuroMemConfig

        config = NeuroMemConfig("neuromem.yaml")
        wf = config.workflows()
        cron = wf.get("cron", {})

        assert "consolidation" in cron
        assert "decay" in cron
        assert "optimization" in cron
        assert "health_check" in cron

    def test_config_concurrency(self):
        """Test concurrency configuration."""
        from neuromem.config import NeuroMemConfig

        config = NeuroMemConfig("neuromem.yaml")
        wf = config.workflows()
        concurrency = wf.get("concurrency", {})

        assert "observe" in concurrency
        assert isinstance(concurrency["observe"], int)

    def test_config_retries(self):
        """Test retry configuration."""
        from neuromem.config import NeuroMemConfig

        config = NeuroMemConfig("neuromem.yaml")
        wf = config.workflows()
        retries = wf.get("retries", {})

        assert "observe" in retries
        assert "consolidation" in retries


class TestWorkflowClientSingleton:
    """Test Inngest client singleton behavior."""

    def test_reset_client(self):
        """Test client reset."""
        from neuromem.workflows.client import reset_client

        reset_client()  # Should not raise

    def test_get_client_without_inngest_raises(self):
        """Test that get_inngest_client raises ImportError without inngest."""
        from neuromem.workflows.client import INNGEST_AVAILABLE, reset_client

        reset_client()

        if not INNGEST_AVAILABLE:
            with pytest.raises(ImportError, match="inngest"):
                from neuromem.workflows.client import get_inngest_client

                get_inngest_client()


class TestWorkflowEventHelpers:
    """Test event helper functions."""

    def test_send_observe_event_without_inngest(self):
        """Test send_observe_event returns None without inngest."""
        from neuromem.workflows.events import send_observe_event, INNGEST_AVAILABLE

        if not INNGEST_AVAILABLE:
            result = send_observe_event(
                client=None,
                user_input="test",
                assistant_output="response",
                user_id="user_123",
            )
            assert result is None

    def test_send_consolidation_event_without_inngest(self):
        """Test send_consolidation_event returns None without inngest."""
        from neuromem.workflows.events import send_consolidation_event, INNGEST_AVAILABLE

        if not INNGEST_AVAILABLE:
            result = send_consolidation_event(
                client=None,
                user_id="user_123",
                trigger="manual",
            )
            assert result is None

    def test_send_maintenance_event_without_inngest(self):
        """Test send_maintenance_event returns None without inngest."""
        from neuromem.workflows.events import send_maintenance_event, INNGEST_AVAILABLE

        if not INNGEST_AVAILABLE:
            result = send_maintenance_event(client=None)
            assert result is None

    def test_send_batch_ingest_without_inngest(self):
        """Test send_batch_ingest_events returns None without inngest."""
        from neuromem.workflows.events import send_batch_ingest_events, INNGEST_AVAILABLE

        if not INNGEST_AVAILABLE:
            result = send_batch_ingest_events(
                client=None,
                observations=[
                    {
                        "user_input": "test",
                        "assistant_output": "response",
                        "user_id": "u1",
                    }
                ],
            )
            assert result is None


class TestWorkflowStepHandlers:
    """Test the pure step handler functions used by Inngest workflows."""

    @pytest.fixture
    def neuromem_instance(self, tmp_path):
        """Create a NeuroMem instance with in-memory backend."""

        config_content = """
neuromem:
  model:
    embedding: text-embedding-3-large
    consolidation_llm: gpt-4o-mini
  storage:
    database:
      type: memory
  memory:
    decay_enabled: true
    consolidation_interval: 10
  async:
    enabled: false
  retrieval:
    hybrid_enabled: false
  workflows:
    enabled: false
"""
        config_path = tmp_path / "test_neuromem.yaml"
        config_path.write_text(config_content)

        from neuromem import NeuroMem

        user_id = str(uuid.uuid4())
        memory = NeuroMem.from_config(str(config_path), user_id=user_id)
        yield memory
        memory.close()

    def test_get_consolidation_candidates(self, neuromem_instance):
        """Test _get_consolidation_candidates returns correct structure."""
        from neuromem.workflows.functions import _get_consolidation_candidates

        result = _get_consolidation_candidates(neuromem_instance)

        assert isinstance(result, dict)
        assert "count" in result
        assert "ids" in result
        assert isinstance(result["count"], int)
        assert isinstance(result["ids"], list)

    def test_run_consolidation(self, neuromem_instance):
        """Test _run_consolidation executes without error."""
        from neuromem.workflows.functions import _run_consolidation

        result = _run_consolidation(neuromem_instance)

        assert isinstance(result, dict)
        assert "status" in result

    def test_apply_decay(self, neuromem_instance):
        """Test _apply_decay returns correct structure."""
        from neuromem.workflows.functions import _apply_decay

        result = _apply_decay(neuromem_instance)

        assert isinstance(result, dict)
        assert "status" in result
        assert result["status"] == "completed"
        assert "total_checked" in result
        assert "active" in result
        assert "deleted" in result

    def test_should_trigger_consolidation_empty(self, neuromem_instance):
        """Test consolidation threshold with empty memory."""
        from neuromem.workflows.functions import _should_trigger_consolidation

        result = _should_trigger_consolidation(neuromem_instance)
        assert result is False  # No memories, shouldn't trigger

    def test_store_observation(self, neuromem_instance):
        """Test _store_observation creates a memory."""
        from neuromem.workflows.functions import _store_observation

        memory_id = _store_observation(
            neuromem_instance,
            user_input="I like Python",
            assistant_output="Python is great!",
            user_id=neuromem_instance.user_id,
            embedding=None,  # Will use mock fallback
            enrichment=None,
        )

        assert isinstance(memory_id, str)
        assert len(memory_id) == 36  # UUID format

        # Verify memory was stored
        memories = neuromem_instance.list(memory_type="episodic", limit=10)
        assert len(memories) >= 1

    def test_auto_tag_without_openai(self, neuromem_instance):
        """Test _auto_tag returns empty enrichment without OpenAI."""
        from neuromem.workflows.functions import _auto_tag

        result = _auto_tag(
            neuromem_instance,
            user_input="I like Python",
            assistant_output="Great choice!",
        )

        assert isinstance(result, dict)
        assert "tags" in result

    def test_run_health_check(self, neuromem_instance):
        """Test _run_health_check returns status."""
        from neuromem.workflows.functions import _run_health_check

        result = _run_health_check(neuromem_instance)

        assert isinstance(result, dict)
        assert "status" in result
        assert result["status"] in ["healthy", "degraded", "unhealthy"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
