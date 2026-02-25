"""Tests for Meta Ad Library token refresh."""
import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from services.meta_ad_library import MetaAdLibraryService


class TestMetaTokenRefresh:
    def setup_method(self):
        self.service = MetaAdLibraryService()

    @pytest.mark.asyncio
    async def test_refresh_no_current_token(self):
        """Fails gracefully when no current token is set."""
        with patch.object(
            type(self.service), "meta_token",
            new_callable=lambda: property(lambda self: ""),
        ):
            result = await self.service.refresh_long_lived_token()
        assert result["success"] is False
        assert "No current" in result["error"]

    @pytest.mark.asyncio
    async def test_refresh_no_app_id(self):
        """Fails gracefully when META_APP_ID is missing."""
        with patch.object(
            type(self.service), "meta_token",
            new_callable=lambda: property(lambda self: "valid_token"),
        ):
            with patch("services.meta_ad_library.settings") as mock_settings:
                mock_settings.META_APP_ID = ""
                mock_settings.META_APP_SECRET = "secret"
                result = await self.service.refresh_long_lived_token()
        assert result["success"] is False
        assert "META_APP_ID" in result["error"]

    @pytest.mark.asyncio
    async def test_refresh_no_app_secret(self):
        """Fails gracefully when META_APP_SECRET is missing."""
        with patch.object(
            type(self.service), "meta_token",
            new_callable=lambda: property(lambda self: "valid_token"),
        ):
            with patch("services.meta_ad_library.settings") as mock_settings:
                mock_settings.META_APP_ID = "123456"
                mock_settings.META_APP_SECRET = ""
                result = await self.service.refresh_long_lived_token()
        assert result["success"] is False
        assert "META_APP_SECRET" in result["error"]

    @pytest.mark.asyncio
    async def test_refresh_success(self):
        """Successful token refresh updates env and SSM."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "access_token": "new_long_lived_token_abc",
            "token_type": "bearer",
            "expires_in": 5184000,  # 60 days
        }

        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch.object(
            type(self.service), "meta_token",
            new_callable=lambda: property(lambda self: "old_token"),
        ):
            with patch("services.meta_ad_library.settings") as mock_settings:
                mock_settings.META_APP_ID = "1412476120256167"
                mock_settings.META_APP_SECRET = "test_secret"
                with patch("httpx.AsyncClient.__aenter__", return_value=mock_client):
                    with patch.object(
                        self.service, "_update_ssm_token", new_callable=AsyncMock
                    ) as mock_ssm:
                        with patch.dict("os.environ", {}, clear=False):
                            result = await self.service.refresh_long_lived_token()

        assert result["success"] is True
        assert result["expires_in"] == 5184000
        assert result["expires_days"] == 60
        mock_ssm.assert_called_once_with("new_long_lived_token_abc")

    @pytest.mark.asyncio
    async def test_refresh_no_access_token_in_response(self):
        """Handles response without access_token."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {"error": "something weird"}

        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch.object(
            type(self.service), "meta_token",
            new_callable=lambda: property(lambda self: "old_token"),
        ):
            with patch("services.meta_ad_library.settings") as mock_settings:
                mock_settings.META_APP_ID = "123"
                mock_settings.META_APP_SECRET = "secret"
                with patch("httpx.AsyncClient.__aenter__", return_value=mock_client):
                    result = await self.service.refresh_long_lived_token()

        assert result["success"] is False
        assert "No access_token" in result["error"]

    @pytest.mark.asyncio
    async def test_refresh_http_error(self):
        """Handles HTTP errors from Facebook API."""
        import httpx

        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = '{"error":{"message":"Invalid token"}}'

        mock_client = MagicMock()
        mock_client.get = AsyncMock(
            side_effect=httpx.HTTPStatusError(
                "Bad Request", request=MagicMock(), response=mock_response
            )
        )

        with patch.object(
            type(self.service), "meta_token",
            new_callable=lambda: property(lambda self: "expired_token"),
        ):
            with patch("services.meta_ad_library.settings") as mock_settings:
                mock_settings.META_APP_ID = "123"
                mock_settings.META_APP_SECRET = "secret"
                with patch("httpx.AsyncClient.__aenter__", return_value=mock_client):
                    result = await self.service.refresh_long_lived_token()

        assert result["success"] is False
        assert "HTTP 400" in result["error"]

    @pytest.mark.asyncio
    async def test_refresh_ssm_failure_propagates(self):
        """If SSM update fails, the whole refresh reports failure."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        mock_response.json.return_value = {
            "access_token": "new_token",
            "expires_in": 5184000,
        }

        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=mock_response)

        with patch.object(
            type(self.service), "meta_token",
            new_callable=lambda: property(lambda self: "old_token"),
        ):
            with patch("services.meta_ad_library.settings") as mock_settings:
                mock_settings.META_APP_ID = "123"
                mock_settings.META_APP_SECRET = "secret"
                with patch("httpx.AsyncClient.__aenter__", return_value=mock_client):
                    with patch.object(
                        self.service, "_update_ssm_token", new_callable=AsyncMock,
                        side_effect=Exception("SSM access denied"),
                    ):
                        with patch.dict("os.environ", {}, clear=False):
                            result = await self.service.refresh_long_lived_token()

        assert result["success"] is False
        assert "SSM access denied" in result["error"]

    @pytest.mark.asyncio
    async def test_update_ssm_token_calls_boto3(self):
        """SSM update calls boto3 put_parameter with correct args."""
        mock_ssm_client = MagicMock()
        mock_boto3 = MagicMock()
        mock_boto3.client.return_value = mock_ssm_client

        with patch.dict("sys.modules", {"boto3": mock_boto3}):
            await self.service._update_ssm_token("test_new_token")

        mock_boto3.client.assert_called_once_with("ssm", region_name="eu-central-1")
        mock_ssm_client.put_parameter.assert_called_once_with(
            Name="/panoramai/prod/META_AD_LIBRARY_TOKEN",
            Value="test_new_token",
            Type="SecureString",
            Overwrite=True,
        )


class TestSchedulerMetaTokenJob:
    """Test that the scheduler correctly wires up the monthly token refresh."""

    def test_scheduler_has_meta_token_refresh_job(self):
        """Scheduler includes the monthly Meta token refresh job."""
        from services.scheduler import DataCollectionScheduler
        sched = DataCollectionScheduler()
        job_ids = [job.id for job in sched.scheduler.get_jobs()]
        assert "monthly_meta_token_refresh" in job_ids

    def test_scheduler_meta_token_job_runs_on_first_of_month(self):
        """The Meta token refresh job is scheduled for day=1."""
        from services.scheduler import DataCollectionScheduler
        sched = DataCollectionScheduler()
        job = sched.scheduler.get_job("monthly_meta_token_refresh")
        assert job is not None
        trigger = job.trigger
        # CronTrigger fields: check day=1, hour=4
        assert str(trigger) == "cron[day='1', hour='4', minute='0']" or "day='1'" in str(trigger)
