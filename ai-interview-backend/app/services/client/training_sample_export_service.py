from typing import Any, Dict, Optional, Sequence


class TrainingSampleExportService:
    """Export-facing facade for training sample and fine-tuning bundle logic.

    The first extraction step keeps persistence and interview orchestration in
    InterviewService, while routing export callers through this bounded service.
    """

    @staticmethod
    def get_training_sample_review(panel_snapshot: Any) -> Dict[str, Any]:
        from app.services.client.interview_service import InterviewService

        return InterviewService.get_training_sample_review(panel_snapshot)

    @staticmethod
    def build_training_sample(
        interview: Any,
        messages: Sequence[Any] | None = None,
        user_email: str | None = None,
        include_user_email: bool = False,
    ) -> Dict[str, Any]:
        from app.services.client.interview_service import InterviewService

        return InterviewService.build_training_sample(
            interview=interview,
            messages=messages,
            user_email=user_email,
            include_user_email=include_user_email,
        )

    @staticmethod
    def is_export_ready_training_sample(sample: Dict[str, Any]) -> bool:
        from app.services.client.interview_service import InterviewService

        return InterviewService.is_export_ready_training_sample(sample)

    @staticmethod
    def build_fine_tuning_dataset_bundle(samples: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
        from app.services.client.interview_service import InterviewService

        return InterviewService.build_fine_tuning_dataset_bundle(samples)

    @staticmethod
    def build_fine_tuning_readiness_report(samples: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
        from app.services.client.interview_service import InterviewService

        return InterviewService.build_fine_tuning_readiness_report(samples)

    @staticmethod
    def build_fine_tuning_record(sample: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        from app.services.client.interview_service import InterviewService

        return InterviewService._build_fine_tuning_record(sample)


training_sample_export_service = TrainingSampleExportService()
