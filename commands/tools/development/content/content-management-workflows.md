______________________________________________________________________

title: Content Management Workflows
owner: Developer Enablement Guild
last_reviewed: 2025-02-06
supported_platforms:

- macOS
- Linux
  required_scripts: []
  risk: medium
  status: active
  id: 01K6EEXC470WJWDGXFSKX74911
  category: development/content

______________________________________________________________________

## Content Management Workflows & Automation

You are a content management expert specializing in automated content workflows, multi-language support, content validation, and publishing automation. Create comprehensive content management systems that handle the full content lifecycle from creation to publication.

## Context

The user needs to implement content management workflows including automated content processing, multi-language localization, content validation, SEO optimization, and automated publishing pipelines for various content types and platforms.

## Requirements

$ARGUMENTS

## Instructions

### 1. Multi-Agent Content Management Strategy

Execute comprehensive content management using specialized agents:

**Content Strategy & Architecture**
Use Task tool with subagent_type="architecture-council" to:

- Design content management system architecture
- Create content modeling and taxonomy systems
- Implement content versioning and workflow systems
- Set up content API and data layer architecture

Prompt: "Design content management system architecture for: $ARGUMENTS. Include:

1. Content modeling, taxonomy, and metadata systems
1. Content versioning and revision control workflows
1. Multi-tenant content architecture and permissions
1. Content API design and data layer optimization"

**Frontend Content Management**
Use Task tool with subagent_type="frontend-developer" to:

- Build content editing interfaces
- Create content preview and publishing systems
- Implement responsive content management dashboards
- Set up real-time collaborative editing features

Prompt: "Create content management frontend for: $ARGUMENTS. Focus on:

1. Rich content editing interfaces and WYSIWYG editors
1. Content preview and publishing workflow UI
1. Responsive content management dashboards
1. Real-time collaborative editing and commenting systems"

**Automation & Workflow Orchestration**
Use Task tool with subagent_type="architecture-council" to:

- Create automated content processing pipelines
- Implement content validation and quality checks
- Set up automated publishing and distribution
- Build content analytics and optimization systems

Prompt: "Create content automation workflows for: $ARGUMENTS. Include:

1. Automated content processing and transformation pipelines
1. Content validation, quality checks, and compliance systems
1. Automated publishing and multi-channel distribution
1. Content analytics, SEO optimization, and performance tracking"

### 2. Comprehensive Content Management Framework

**Advanced Content Management System**

```python
from typing import Dict, List, Any, Optional, Union, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from abc import ABC, abstractmethod
import asyncio
import json
import yaml
import hashlib
import re
from pathlib import Path
import uuid
from slugify import slugify


class ContentType(Enum):
    ARTICLE = "article"
    PAGE = "page"
    BLOG_POST = "blog_post"
    PRODUCT = "product"
    DOCUMENTATION = "documentation"
    NEWSLETTER = "newsletter"
    LANDING_PAGE = "landing_page"
    FAQ = "faq"
    CASE_STUDY = "case_study"
    WHITEPAPER = "whitepaper"


class ContentStatus(Enum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    PUBLISHED = "published"
    ARCHIVED = "archived"
    REJECTED = "rejected"


class WorkflowStage(Enum):
    CREATION = "creation"
    EDITING = "editing"
    REVIEW = "review"
    APPROVAL = "approval"
    LOCALIZATION = "localization"
    SEO_OPTIMIZATION = "seo_optimization"
    PUBLICATION = "publication"
    DISTRIBUTION = "distribution"


@dataclass
class ContentMetadata:
    """Comprehensive content metadata"""

    title: str
    description: str
    author: str
    created_at: datetime
    updated_at: datetime
    tags: List[str] = field(default_factory=list)
    categories: List[str] = field(default_factory=list)
    language: str = "en"
    seo_title: Optional[str] = None
    seo_description: Optional[str] = None
    keywords: List[str] = field(default_factory=list)
    canonical_url: Optional[str] = None
    featured_image: Optional[str] = None
    reading_time: Optional[int] = None  # in minutes
    target_audience: List[str] = field(default_factory=list)
    content_format: str = "markdown"
    custom_fields: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ContentVersion:
    """Content version for revision control"""

    version_id: str
    content: str
    metadata: ContentMetadata
    author: str
    created_at: datetime
    changelog: str
    parent_version: Optional[str] = None
    is_published: bool = False
    diff_summary: Optional[str] = None


@dataclass
class ContentWorkflow:
    """Content workflow definition"""

    workflow_id: str
    name: str
    description: str
    stages: List[WorkflowStage]
    rules: Dict[str, Any]
    notifications: Dict[WorkflowStage, List[str]]
    automation: Dict[WorkflowStage, List[str]]
    sla: Dict[WorkflowStage, int]  # Hours for each stage


class ContentManagementSystem:
    """Advanced Content Management System"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.content_store = self.initialize_content_store()
        self.workflow_engine = ContentWorkflowEngine(config.get("workflows", {}))
        self.localization_manager = LocalizationManager(config.get("localization", {}))
        self.seo_optimizer = SEOOptimizer(config.get("seo", {}))
        self.publishing_manager = PublishingManager(config.get("publishing", {}))
        self.analytics_tracker = ContentAnalyticsTracker(config.get("analytics", {}))
        self.validation_engine = ContentValidationEngine(config.get("validation", {}))

    def initialize_content_store(self):
        """Initialize content storage system"""
        storage_type = self.config.get("storage", {}).get("type", "file")

        if storage_type == "database":
            return DatabaseContentStore(self.config["storage"])
        elif storage_type == "headless_cms":
            return HeadlessCMSStore(self.config["storage"])
        elif storage_type == "git":
            return GitContentStore(self.config["storage"])
        else:
            return FileContentStore(self.config["storage"])

    async def create_content(
        self,
        content_type: ContentType,
        content_data: Dict[str, Any],
        author: str,
        workflow_id: Optional[str] = None,
    ) -> str:
        """Create new content with workflow"""

        # Generate content ID
        content_id = str(uuid.uuid4())

        # Create metadata
        metadata = ContentMetadata(
            title=content_data.get("title", ""),
            description=content_data.get("description", ""),
            author=author,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            tags=content_data.get("tags", []),
            categories=content_data.get("categories", []),
            language=content_data.get("language", "en"),
            seo_title=content_data.get("seo_title"),
            seo_description=content_data.get("seo_description"),
            keywords=content_data.get("keywords", []),
            canonical_url=content_data.get("canonical_url"),
            featured_image=content_data.get("featured_image"),
            target_audience=content_data.get("target_audience", []),
            content_format=content_data.get("format", "markdown"),
            custom_fields=content_data.get("custom_fields", {}),
        )

        # Create initial version
        initial_version = ContentVersion(
            version_id=f"{content_id}_v1",
            content=content_data.get("content", ""),
            metadata=metadata,
            author=author,
            created_at=datetime.now(timezone.utc),
            changelog="Initial version",
        )

        # Store content
        await self.content_store.save_content(content_id, content_type, initial_version)

        # Start workflow if specified
        if workflow_id:
            await self.workflow_engine.start_workflow(content_id, workflow_id, author)

        # Track creation analytics
        await self.analytics_tracker.track_content_creation(
            content_id, content_type, author
        )

        return content_id

    async def update_content(
        self, content_id: str, updates: Dict[str, Any], author: str, changelog: str = ""
    ) -> str:
        """Update content with versioning"""

        # Get current content
        current_content = await self.content_store.get_content(content_id)
        if not current_content:
            raise ValueError(f"Content {content_id} not found")

        # Create new version
        current_version = current_content["versions"][-1]
        new_version_num = len(current_content["versions"]) + 1

        # Update metadata
        updated_metadata = current_version.metadata
        for key, value in updates.get("metadata", {}).items():
            if hasattr(updated_metadata, key):
                setattr(updated_metadata, key, value)
        updated_metadata.updated_at = datetime.now(timezone.utc)

        # Create new version
        new_version = ContentVersion(
            version_id=f"{content_id}_v{new_version_num}",
            content=updates.get("content", current_version.content),
            metadata=updated_metadata,
            author=author,
            created_at=datetime.now(timezone.utc),
            changelog=changelog or f"Updated by {author}",
            parent_version=current_version.version_id,
        )

        # Generate diff summary
        new_version.diff_summary = self.generate_diff_summary(
            current_version.content, new_version.content
        )

        # Save updated content
        await self.content_store.update_content(content_id, new_version)

        # Track update analytics
        await self.analytics_tracker.track_content_update(
            content_id, author, new_version.version_id
        )

        return new_version.version_id

    def generate_diff_summary(self, old_content: str, new_content: str) -> str:
        """Generate human-readable diff summary"""
        import difflib

        old_lines = old_content.splitlines()
        new_lines = new_content.splitlines()

        differ = difflib.unified_diff(
            old_lines, new_lines, fromfile="old", tofile="new", lineterm=""
        )

        changes = list(differ)

        if not changes:
            return "No changes"

        additions = len([line for line in changes if line.startswith("+")])
        deletions = len([line for line in changes if line.startswith("-")])

        return f"Added {additions} lines, removed {deletions} lines"

    async def process_content_workflow(
        self,
        content_id: str,
        stage: WorkflowStage,
        actor: str,
        data: Dict[str, Any] = None,
    ) -> Dict[str, Any]:
        """Process content through workflow stage"""

        workflow_result = await self.workflow_engine.process_stage(
            content_id, stage, actor, data or {}
        )

        # Apply stage-specific processing
        if stage == WorkflowStage.SEO_OPTIMIZATION:
            seo_result = await self.seo_optimizer.optimize_content(content_id)
            workflow_result["seo_optimization"] = seo_result

        elif stage == WorkflowStage.LOCALIZATION:
            localization_result = await self.localization_manager.initiate_localization(
                content_id, data.get("target_languages", [])
            )
            workflow_result["localization"] = localization_result

        elif stage == WorkflowStage.PUBLICATION:
            publication_result = await self.publishing_manager.publish_content(
                content_id, data.get("channels", [])
            )
            workflow_result["publication"] = publication_result

        return workflow_result


class ContentWorkflowEngine:
    """Content workflow automation engine"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.workflows = self.load_workflows()
        self.active_workflows = {}
        self.notification_service = NotificationService(config.get("notifications", {}))

    def load_workflows(self) -> Dict[str, ContentWorkflow]:
        """Load workflow definitions"""
        workflows = {}

        # Default editorial workflow
        editorial_workflow = ContentWorkflow(
            workflow_id="editorial",
            name="Editorial Workflow",
            description="Standard editorial review and publishing workflow",
            stages=[
                WorkflowStage.CREATION,
                WorkflowStage.EDITING,
                WorkflowStage.REVIEW,
                WorkflowStage.APPROVAL,
                WorkflowStage.SEO_OPTIMIZATION,
                WorkflowStage.PUBLICATION,
            ],
            rules={
                "min_reviewers": 2,
                "approval_required": True,
                "seo_score_threshold": 70,
                "auto_publish": False,
            },
            notifications={
                WorkflowStage.REVIEW: ["editors@company.com"],
                WorkflowStage.APPROVAL: ["content-manager@company.com"],
                WorkflowStage.PUBLICATION: ["marketing@company.com"],
            },
            automation={
                WorkflowStage.SEO_OPTIMIZATION: [
                    "auto_seo_check",
                    "readability_analysis",
                ],
                WorkflowStage.PUBLICATION: [
                    "social_media_post",
                    "newsletter_inclusion",
                ],
            },
            sla={
                WorkflowStage.EDITING: 24,
                WorkflowStage.REVIEW: 48,
                WorkflowStage.APPROVAL: 24,
                WorkflowStage.SEO_OPTIMIZATION: 12,
                WorkflowStage.PUBLICATION: 6,
            },
        )
        workflows["editorial"] = editorial_workflow

        # Localization workflow
        localization_workflow = ContentWorkflow(
            workflow_id="localization",
            name="Localization Workflow",
            description="Multi-language content localization workflow",
            stages=[
                WorkflowStage.CREATION,
                WorkflowStage.REVIEW,
                WorkflowStage.LOCALIZATION,
                WorkflowStage.APPROVAL,
                WorkflowStage.PUBLICATION,
            ],
            rules={
                "source_approval_required": True,
                "translation_review_required": True,
                "cultural_adaptation": True,
            },
            notifications={
                WorkflowStage.LOCALIZATION: ["translation-team@company.com"],
                WorkflowStage.REVIEW: ["localization-reviewers@company.com"],
            },
            automation={
                WorkflowStage.LOCALIZATION: [
                    "auto_translation_memory",
                    "terminology_check",
                ]
            },
            sla={
                WorkflowStage.LOCALIZATION: 120,  # 5 days for translation
                WorkflowStage.REVIEW: 48,
                WorkflowStage.APPROVAL: 24,
            },
        )
        workflows["localization"] = localization_workflow

        return workflows

    async def start_workflow(
        self, content_id: str, workflow_id: str, initiator: str
    ) -> Dict[str, Any]:
        """Start content workflow"""

        if workflow_id not in self.workflows:
            raise ValueError(f"Unknown workflow: {workflow_id}")

        workflow = self.workflows[workflow_id]

        workflow_instance = {
            "content_id": content_id,
            "workflow_id": workflow_id,
            "current_stage": workflow.stages[0],
            "stage_index": 0,
            "initiator": initiator,
            "started_at": datetime.now(timezone.utc),
            "stage_history": [],
            "pending_actions": [],
            "metadata": {},
        }

        instance_key = f"{content_id}_{workflow_id}"
        self.active_workflows[instance_key] = workflow_instance

        # Send initial notifications
        await self.send_stage_notifications(workflow_instance, workflow.stages[0])

        return {
            "instance_key": instance_key,
            "current_stage": workflow.stages[0],
            "next_actions": self.get_stage_actions(workflow.stages[0]),
            "sla_deadline": self.calculate_sla_deadline(
                workflow_id, workflow.stages[0]
            ),
        }

    async def process_stage(
        self, content_id: str, stage: WorkflowStage, actor: str, data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Process workflow stage"""

        # Find active workflow instance
        instance = None
        for key, wf_instance in self.active_workflows.items():
            if wf_instance["content_id"] == content_id:
                instance = wf_instance
                break

        if not instance:
            raise ValueError(f"No active workflow found for content {content_id}")

        workflow = self.workflows[instance["workflow_id"]]

        # Validate stage transition
        if not self.can_transition_to_stage(instance, stage):
            raise ValueError(f"Invalid stage transition to {stage}")

        # Process stage-specific logic
        stage_result = await self.execute_stage_logic(instance, stage, actor, data)

        # Update workflow instance
        instance["stage_history"].append(
            {
                "stage": stage,
                "actor": actor,
                "timestamp": datetime.now(timezone.utc),
                "data": data,
                "result": stage_result,
            }
        )

        # Check if workflow is complete
        if stage == workflow.stages[-1]:
            await self.complete_workflow(instance)
        else:
            # Move to next stage if auto-advance
            if stage_result.get("auto_advance", False):
                next_stage_index = workflow.stages.index(stage) + 1
                if next_stage_index < len(workflow.stages):
                    instance["current_stage"] = workflow.stages[next_stage_index]
                    instance["stage_index"] = next_stage_index

        return stage_result


class LocalizationManager:
    """Content localization and translation management"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.translation_memory = TranslationMemory(
            config.get("translation_memory", {})
        )
        self.translation_providers = self.initialize_providers()
        self.terminology_database = TerminologyDatabase(config.get("terminology", {}))

    def initialize_providers(self):
        """Initialize translation service providers"""
        providers = {}

        # Google Translate provider
        if "google_translate" in self.config:
            providers["google"] = GoogleTranslateProvider(
                self.config["google_translate"]
            )

        # DeepL provider
        if "deepl" in self.config:
            providers["deepl"] = DeepLProvider(self.config["deepl"])

        # Human translation provider
        if "human_translation" in self.config:
            providers["human"] = HumanTranslationProvider(
                self.config["human_translation"]
            )

        return providers

    async def initiate_localization(
        self, content_id: str, target_languages: List[str]
    ) -> Dict[str, Any]:
        """Initiate content localization process"""

        localization_jobs = []

        for language in target_languages:
            job = await self.create_localization_job(content_id, language)
            localization_jobs.append(job)

        return {
            "localization_id": str(uuid.uuid4()),
            "content_id": content_id,
            "target_languages": target_languages,
            "jobs": localization_jobs,
            "started_at": datetime.now(timezone.utc),
            "status": "in_progress",
        }

    async def create_localization_job(
        self, content_id: str, target_language: str
    ) -> Dict[str, Any]:
        """Create individual localization job"""

        # Analyze content for localization requirements
        analysis = await self.analyze_content_for_localization(
            content_id, target_language
        )

        # Select appropriate translation provider
        provider = self.select_translation_provider(analysis)

        # Create translation job
        job = {
            "job_id": str(uuid.uuid4()),
            "content_id": content_id,
            "target_language": target_language,
            "provider": provider["name"],
            "analysis": analysis,
            "created_at": datetime.now(timezone.utc),
            "status": "pending",
            "estimated_completion": self.estimate_completion_time(analysis, provider),
        }

        return job

    async def analyze_content_for_localization(
        self, content_id: str, target_language: str
    ) -> Dict[str, Any]:
        """Analyze content complexity and localization requirements"""

        # This would analyze:
        # - Word count and complexity
        # - Technical terminology
        # - Cultural adaptation needs
        # - Multimedia content
        # - SEO requirements

        return {
            "word_count": 1500,
            "complexity": "medium",
            "technical_terms": 45,
            "cultural_adaptation_needed": True,
            "multimedia_elements": 3,
            "seo_keywords": 12,
        }


class SEOOptimizer:
    """SEO optimization and content analysis"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.seo_tools = self.initialize_seo_tools()
        self.keyword_analyzer = KeywordAnalyzer(config.get("keywords", {}))

    async def optimize_content(self, content_id: str) -> Dict[str, Any]:
        """Perform comprehensive SEO optimization"""

        optimization_result = {
            "content_id": content_id,
            "optimized_at": datetime.now(timezone.utc),
            "scores": {},
            "recommendations": [],
            "optimizations_applied": [],
        }

        # Get content
        content = await self.get_content(content_id)

        # Analyze SEO factors
        seo_analysis = await self.analyze_seo_factors(content)
        optimization_result["scores"] = seo_analysis["scores"]

        # Generate recommendations
        recommendations = await self.generate_seo_recommendations(content, seo_analysis)
        optimization_result["recommendations"] = recommendations

        # Apply automatic optimizations
        auto_optimizations = await self.apply_automatic_optimizations(
            content, recommendations
        )
        optimization_result["optimizations_applied"] = auto_optimizations

        return optimization_result

    async def analyze_seo_factors(self, content: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze various SEO factors"""

        analysis = {"scores": {}, "factors": {}}

        # Title optimization
        title_score = self.analyze_title_seo(content["metadata"]["title"])
        analysis["scores"]["title"] = title_score

        # Meta description
        meta_desc_score = self.analyze_meta_description(
            content["metadata"].get("seo_description", "")
        )
        analysis["scores"]["meta_description"] = meta_desc_score

        # Content structure
        structure_score = self.analyze_content_structure(content["content"])
        analysis["scores"]["content_structure"] = structure_score

        # Keyword optimization
        keyword_score = await self.analyze_keyword_optimization(content)
        analysis["scores"]["keyword_optimization"] = keyword_score

        # Readability
        readability_score = self.analyze_readability(content["content"])
        analysis["scores"]["readability"] = readability_score

        # Calculate overall SEO score
        overall_score = sum(analysis["scores"].values()) / len(analysis["scores"])
        analysis["scores"]["overall"] = overall_score

        return analysis

    def analyze_title_seo(self, title: str) -> float:
        """Analyze title SEO effectiveness"""
        score = 0

        # Length check (50-60 characters optimal)
        length = len(title)
        if 50 <= length <= 60:
            score += 30
        elif 40 <= length <= 70:
            score += 20
        else:
            score += 10

        # Contains numbers
        if any(char.isdigit() for char in title):
            score += 10

        # Power words
        power_words = ["ultimate", "complete", "guide", "best", "top", "essential"]
        if any(word in title.lower() for word in power_words):
            score += 15

        # Question format
        if title.startswith(("How", "What", "Why", "When", "Where")):
            score += 10

        return min(score, 100)

    def analyze_readability(self, content: str) -> float:
        """Analyze content readability"""

        # Simple readability metrics
        sentences = content.split(".")
        words = content.split()

        if not sentences or not words:
            return 0

        avg_sentence_length = len(words) / len(sentences)

        # Flesch Reading Ease approximation
        score = 206.835 - 1.015 * avg_sentence_length

        # Convert to 0-100 scale
        return max(0, min(100, score))


class PublishingManager:
    """Content publishing and distribution management"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.channels = self.initialize_publishing_channels()
        self.scheduler = PublishingScheduler(config.get("scheduler", {}))

    def initialize_publishing_channels(self):
        """Initialize publishing channels"""
        channels = {}

        # Website/CMS publishing
        if "website" in self.config:
            channels["website"] = WebsitePublisher(self.config["website"])

        # Social media publishing
        if "social_media" in self.config:
            channels["social_media"] = SocialMediaPublisher(self.config["social_media"])

        # Email newsletter
        if "newsletter" in self.config:
            channels["newsletter"] = NewsletterPublisher(self.config["newsletter"])

        # API/Headless publishing
        if "api" in self.config:
            channels["api"] = APIPublisher(self.config["api"])

        return channels

    async def publish_content(
        self, content_id: str, channels: List[str] = None
    ) -> Dict[str, Any]:
        """Publish content to specified channels"""

        channels_to_publish = channels or list(self.channels.keys())

        publication_result = {
            "content_id": content_id,
            "published_at": datetime.now(timezone.utc),
            "channels": {},
            "overall_status": "success",
        }

        for channel_name in channels_to_publish:
            if channel_name not in self.channels:
                publication_result["channels"][channel_name] = {
                    "status": "error",
                    "error": f"Unknown channel: {channel_name}",
                }
                continue

            try:
                channel = self.channels[channel_name]
                result = await channel.publish(content_id)
                publication_result["channels"][channel_name] = result

            except Exception as e:
                publication_result["channels"][channel_name] = {
                    "status": "error",
                    "error": str(e),
                }
                publication_result["overall_status"] = "partial"

        return publication_result
```

### 3. Automated Content Processing Pipeline

**Content Processing and Validation Engine**

```python
class ContentProcessingPipeline:
    """Automated content processing and validation pipeline"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.processors = self.initialize_processors()
        self.validators = self.initialize_validators()
        self.transformers = self.initialize_transformers()

    def initialize_processors(self):
        """Initialize content processors"""
        return {
            "markdown": MarkdownProcessor(),
            "html": HTMLProcessor(),
            "image": ImageProcessor(self.config.get("image_processing", {})),
            "video": VideoProcessor(self.config.get("video_processing", {})),
            "pdf": PDFProcessor(),
            "text": TextProcessor(),
        }

    def initialize_validators(self):
        """Initialize content validators"""
        return {
            "accessibility": AccessibilityValidator(),
            "grammar": GrammarValidator(self.config.get("grammar", {})),
            "plagiarism": PlagiarismValidator(self.config.get("plagiarism", {})),
            "brand_compliance": BrandComplianceValidator(self.config.get("brand", {})),
            "legal_compliance": LegalComplianceValidator(self.config.get("legal", {})),
            "seo": SEOValidator(self.config.get("seo_validation", {})),
        }

    async def process_content(
        self, content_id: str, processing_options: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Process content through automated pipeline"""

        options = processing_options or {}

        pipeline_result = {
            "content_id": content_id,
            "processed_at": datetime.now(timezone.utc),
            "stages": {},
            "overall_status": "success",
            "processing_time": 0,
        }

        start_time = time.time()

        try:
            # Stage 1: Content Analysis
            analysis_result = await self.analyze_content(content_id)
            pipeline_result["stages"]["analysis"] = analysis_result

            # Stage 2: Content Validation
            if options.get("validate", True):
                validation_result = await self.validate_content(content_id)
                pipeline_result["stages"]["validation"] = validation_result

                if validation_result["has_errors"]:
                    pipeline_result["overall_status"] = "validation_failed"
                    return pipeline_result

            # Stage 3: Content Transformation
            if options.get("transform", True):
                transformation_result = await self.transform_content(
                    content_id, options
                )
                pipeline_result["stages"]["transformation"] = transformation_result

            # Stage 4: Asset Processing
            if options.get("process_assets", True):
                asset_result = await self.process_assets(content_id)
                pipeline_result["stages"]["asset_processing"] = asset_result

            # Stage 5: Optimization
            if options.get("optimize", True):
                optimization_result = await self.optimize_content(content_id)
                pipeline_result["stages"]["optimization"] = optimization_result

            # Stage 6: Quality Assurance
            if options.get("quality_check", True):
                qa_result = await self.quality_assurance_check(content_id)
                pipeline_result["stages"]["quality_assurance"] = qa_result

        except Exception as e:
            pipeline_result["overall_status"] = "error"
            pipeline_result["error"] = str(e)

        finally:
            pipeline_result["processing_time"] = time.time() - start_time

        return pipeline_result

    async def analyze_content(self, content_id: str) -> Dict[str, Any]:
        """Analyze content structure and characteristics"""

        content = await self.get_content(content_id)

        analysis = {
            "content_type": self.detect_content_type(content),
            "language": self.detect_language(content["content"]),
            "word_count": len(content["content"].split()),
            "reading_time": self.calculate_reading_time(content["content"]),
            "complexity_score": self.analyze_complexity(content["content"]),
            "headings_structure": self.analyze_headings(content["content"]),
            "links": self.extract_links(content["content"]),
            "images": self.extract_images(content["content"]),
            "keywords": self.extract_keywords(content["content"]),
            "sentiment": self.analyze_sentiment(content["content"]),
        }

        return analysis

    async def validate_content(self, content_id: str) -> Dict[str, Any]:
        """Run comprehensive content validation"""

        validation_result = {
            "content_id": content_id,
            "validated_at": datetime.now(timezone.utc),
            "validators": {},
            "has_errors": False,
            "has_warnings": False,
            "summary": {
                "total_issues": 0,
                "errors": 0,
                "warnings": 0,
                "suggestions": 0,
            },
        }

        for validator_name, validator in self.validators.items():
            try:
                result = await validator.validate(content_id)
                validation_result["validators"][validator_name] = result

                # Update summary
                if result.get("errors"):
                    validation_result["has_errors"] = True
                    validation_result["summary"]["errors"] += len(result["errors"])

                if result.get("warnings"):
                    validation_result["has_warnings"] = True
                    validation_result["summary"]["warnings"] += len(result["warnings"])

                if result.get("suggestions"):
                    validation_result["summary"]["suggestions"] += len(
                        result["suggestions"]
                    )

            except Exception as e:
                validation_result["validators"][validator_name] = {
                    "status": "error",
                    "error": str(e),
                }

        validation_result["summary"]["total_issues"] = (
            validation_result["summary"]["errors"]
            + validation_result["summary"]["warnings"]
            + validation_result["summary"]["suggestions"]
        )

        return validation_result


class AccessibilityValidator:
    """Content accessibility validation"""

    async def validate(self, content_id: str) -> Dict[str, Any]:
        """Validate content accessibility"""

        content = await self.get_content(content_id)

        validation_result = {
            "status": "passed",
            "errors": [],
            "warnings": [],
            "suggestions": [],
        }

        # Check alt text for images
        images_without_alt = self.check_images_alt_text(content["content"])
        if images_without_alt:
            validation_result["errors"].extend(
                [f"Image missing alt text: {img}" for img in images_without_alt]
            )

        # Check heading structure
        heading_issues = self.check_heading_structure(content["content"])
        validation_result["warnings"].extend(heading_issues)

        # Check color contrast (if HTML content)
        if content.get("format") == "html":
            contrast_issues = self.check_color_contrast(content["content"])
            validation_result["warnings"].extend(contrast_issues)

        # Check link descriptions
        link_issues = self.check_link_accessibility(content["content"])
        validation_result["suggestions"].extend(link_issues)

        if validation_result["errors"]:
            validation_result["status"] = "failed"
        elif validation_result["warnings"]:
            validation_result["status"] = "warning"

        return validation_result

    def check_images_alt_text(self, content: str) -> List[str]:
        """Check for images without alt text"""
        import re

        # Find markdown images without alt text
        markdown_images = re.findall(r"!\[\s*\]\([^)]+\)", content)

        # Find HTML img tags without alt attribute
        html_images = re.findall(r"<img(?![^>]*alt=)[^>]*>", content, re.IGNORECASE)

        return markdown_images + html_images


class GrammarValidator:
    """Grammar and style validation"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        # Initialize grammar checking tools (LanguageTool, Grammarly API, etc.)

    async def validate(self, content_id: str) -> Dict[str, Any]:
        """Validate grammar and style"""

        content = await self.get_content(content_id)
        text_content = self.extract_text_content(content["content"])

        validation_result = {
            "status": "passed",
            "errors": [],
            "warnings": [],
            "suggestions": [],
        }

        # Grammar check
        grammar_issues = await self.check_grammar(text_content)
        validation_result["errors"].extend(grammar_issues.get("errors", []))
        validation_result["warnings"].extend(grammar_issues.get("warnings", []))

        # Style check
        style_issues = await self.check_style(text_content)
        validation_result["suggestions"].extend(style_issues.get("suggestions", []))

        # Readability check
        readability_score = self.calculate_readability_score(text_content)
        if readability_score < self.config.get("min_readability_score", 60):
            validation_result["warnings"].append(
                f"Readability score ({readability_score}) below threshold"
            )

        return validation_result


class BrandComplianceValidator:
    """Brand guidelines and compliance validation"""

    def __init__(self, config: Dict[str, Any]):
        self.brand_guidelines = config.get("guidelines", {})
        self.terminology = config.get("approved_terminology", [])
        self.prohibited_terms = config.get("prohibited_terms", [])

    async def validate(self, content_id: str) -> Dict[str, Any]:
        """Validate brand compliance"""

        content = await self.get_content(content_id)

        validation_result = {
            "status": "passed",
            "errors": [],
            "warnings": [],
            "suggestions": [],
        }

        # Check for prohibited terms
        prohibited_found = self.check_prohibited_terms(content["content"])
        if prohibited_found:
            validation_result["errors"].extend(
                [f"Prohibited term found: {term}" for term in prohibited_found]
            )

        # Check terminology compliance
        terminology_issues = self.check_terminology(content["content"])
        validation_result["suggestions"].extend(terminology_issues)

        # Check tone of voice
        tone_issues = self.check_tone_compliance(content["content"])
        validation_result["warnings"].extend(tone_issues)

        return validation_result
```

### 4. Content Analytics & Performance Tracking

**Advanced Content Analytics System**

```javascript
// content-analytics.js
class ContentAnalyticsTracker {
    constructor(config) {
        this.config = config;
        this.analytics_providers = this.initializeProviders();
        this.metrics_collector = new MetricsCollector(config.metrics);
        this.performance_analyzer = new PerformanceAnalyzer(config.performance);
    }
    
    initializeProviders() {
        const providers = {};
        
        if (this.config.google_analytics) {
            providers.google = new GoogleAnalyticsProvider(this.config.google_analytics);
        }
        
        if (this.config.mixpanel) {
            providers.mixpanel = new MixpanelProvider(this.config.mixpanel);
        }
        
        if (this.config.custom_analytics) {
            providers.custom = new CustomAnalyticsProvider(this.config.custom_analytics);
        }
        
        return providers;
    }
    
    async trackContentPerformance(contentId) {
        """Track comprehensive content performance"""
        
        const metrics = {
            contentId,
            timestamp: Date.now(),
            engagement: await this.collectEngagementMetrics(contentId),
            seo: await this.collectSEOMetrics(contentId),
            conversion: await this.collectConversionMetrics(contentId),
            social: await this.collectSocialMetrics(contentId),
            technical: await this.collectTechnicalMetrics(contentId)
        };
        
        // Store metrics
        await this.storeMetrics(contentId, metrics);
        
        // Generate insights
        const insights = await this.generateInsights(contentId, metrics);
        
        return {
            metrics,
            insights,
            recommendations: await this.generateRecommendations(contentId, metrics, insights)
        };
    }
    
    async collectEngagementMetrics(contentId) {
        """Collect user engagement metrics"""
        
        const engagement = {
            pageviews: 0,
            unique_visitors: 0,
            time_on_page: 0,
            bounce_rate: 0,
            scroll_depth: 0,
            click_through_rate: 0,
            comment_count: 0,
            share_count: 0,
            like_count: 0,
            reading_completion_rate: 0
        };
        
        // Collect from all providers
        for (const [providerName, provider] of Object.entries(this.analytics_providers)) {
            try {
                const providerMetrics = await provider.getEngagementMetrics(contentId);
                
                // Aggregate metrics (taking the highest values or averages as appropriate)
                engagement.pageviews += providerMetrics.pageviews || 0;
                engagement.unique_visitors = Math.max(engagement.unique_visitors, providerMetrics.unique_visitors || 0);
                engagement.time_on_page = Math.max(engagement.time_on_page, providerMetrics.time_on_page || 0);
                engagement.bounce_rate = (engagement.bounce_rate + (providerMetrics.bounce_rate || 0)) / 2;
                engagement.scroll_depth = Math.max(engagement.scroll_depth, providerMetrics.scroll_depth || 0);
                engagement.click_through_rate = Math.max(engagement.click_through_rate, providerMetrics.click_through_rate || 0);
                
            } catch (error) {
                console.error(`Error collecting engagement metrics from ${providerName}:`, error);
            }
        }
        
        return engagement;
    }
    
    async collectSEOMetrics(contentId) {
        """Collect SEO performance metrics"""
        
        const seo = {
            organic_traffic: 0,
            keyword_rankings: {},
            search_impressions: 0,
            search_clicks: 0,
            average_position: 0,
            featured_snippets: 0,
            backlinks: 0,
            domain_authority_impact: 0
        };
        
        // Collect from Google Search Console
        if (this.analytics_providers.google) {
            try {
                const searchConsoleData = await this.analytics_providers.google.getSearchConsoleData(contentId);
                seo.organic_traffic = searchConsoleData.clicks || 0;
                seo.search_impressions = searchConsoleData.impressions || 0;
                seo.search_clicks = searchConsoleData.clicks || 0;
                seo.average_position = searchConsoleData.position || 0;
                seo.keyword_rankings = searchConsoleData.keywords || {};
            } catch (error) {
                console.error('Error collecting Google Search Console data:', error);
            }
        }
        
        return seo;
    }
    
    async generateInsights(contentId, metrics) {
        """Generate actionable insights from metrics"""
        
        const insights = {
            performance_category: this.categorizePerformance(metrics),
            top_performing_aspects: [],
            underperforming_aspects: [],
            audience_behavior: this.analyzeAudienceBehavior(metrics),
            content_optimization_opportunities: [],
            trend_analysis: await this.analyzeTrends(contentId, metrics)
        };
        
        // Identify top performing aspects
        if (metrics.engagement.time_on_page > 180) { // 3+ minutes
            insights.top_performing_aspects.push('High engagement time');
        }
        
        if (metrics.engagement.scroll_depth > 75) { // 75%+ scroll
            insights.top_performing_aspects.push('High content consumption');
        }
        
        if (metrics.seo.average_position < 10) { // Top 10 ranking
            insights.top_performing_aspects.push('Strong SEO performance');
        }
        
        // Identify underperforming aspects
        if (metrics.engagement.bounce_rate > 70) {
            insights.underperforming_aspects.push('High bounce rate');
        }
        
        if (metrics.engagement.reading_completion_rate < 30) {
            insights.underperforming_aspects.push('Low reading completion');
        }
        
        if (metrics.social.share_count < 5) {
            insights.underperforming_aspects.push('Limited social sharing');
        }
        
        return insights;
    }
    
    async generateRecommendations(contentId, metrics, insights) {
        """Generate actionable recommendations"""
        
        const recommendations = [];
        
        // Engagement recommendations
        if (metrics.engagement.bounce_rate > 70) {
            recommendations.push({
                type: 'engagement',
                priority: 'high',
                title: 'Reduce Bounce Rate',
                description: 'High bounce rate indicates content may not match user expectations',
                actions: [
                    'Review and improve headline alignment with content',
                    'Enhance opening paragraph to immediately provide value',
                    'Add compelling visual elements above the fold',
                    'Improve page loading speed'
                ]
            });
        }
        
        if (metrics.engagement.time_on_page < 60) {
            recommendations.push({
                type: 'engagement',
                priority: 'medium',
                title: 'Increase Time on Page',
                description: 'Low time on page suggests content needs to be more engaging',
                actions: [
                    'Add interactive elements (polls, quizzes, calculators)',
                    'Include relevant internal links',
                    'Break up text with subheadings and bullet points',
                    'Add multimedia content (images, videos, infographics)'
                ]
            });
        }
        
        // SEO recommendations
        if (metrics.seo.average_position > 20) {
            recommendations.push({
                type: 'seo',
                priority: 'high',
                title: 'Improve Search Rankings',
                description: 'Content is not ranking well in search results',
                actions: [
                    'Optimize title and meta description',
                    'Improve keyword targeting and density',
                    'Add more comprehensive coverage of the topic',
                    'Build high-quality backlinks',
                    'Improve page loading speed and mobile experience'
                ]
            });
        }
        
        // Social sharing recommendations
        if (metrics.social.share_count < 10) {
            recommendations.push({
                type: 'social',
                priority: 'medium',
                title: 'Increase Social Sharing',
                description: 'Content has low social engagement',
                actions: [
                    'Add prominent social sharing buttons',
                    'Create quote graphics for Twitter sharing',
                    'Optimize Open Graph and Twitter Card metadata',
                    'Include shareable statistics or insights',
                    'Create platform-specific content variations'
                ]
            });
        }
        
        return recommendations;
    }
    
    async generatePerformanceReport(contentId, timeRange = '30d') {
        """Generate comprehensive performance report"""
        
        const report = {
            contentId,
            timeRange,
            generatedAt: new Date().toISOString(),
            executiveSummary: {},
            detailedMetrics: {},
            insights: {},
            recommendations: {},
            competitorComparison: {},
            historicalTrends: {}
        };
        
        // Get current metrics
        const currentMetrics = await this.trackContentPerformance(contentId);
        
        // Get historical data
        const historicalData = await this.getHistoricalMetrics(contentId, timeRange);
        
        // Generate executive summary
        report.executiveSummary = this.generateExecutiveSummary(currentMetrics, historicalData);
        
        // Include detailed metrics
        report.detailedMetrics = currentMetrics.metrics;
        report.insights = currentMetrics.insights;
        report.recommendations = currentMetrics.recommendations;
        
        // Add competitor comparison if available
        if (this.config.competitor_tracking) {
            report.competitorComparison = await this.generateCompetitorComparison(contentId);
        }
        
        // Add trend analysis
        report.historicalTrends = await this.analyzeTrends(contentId, currentMetrics.metrics, historicalData);
        
        return report;
    }
}
```

### 5. Multi-Channel Content Distribution

**Automated Content Distribution System**

```python
class MultiChannelDistributor:
    """Automated multi-channel content distribution"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.channels = self.initialize_channels()
        self.scheduler = DistributionScheduler(config.get("scheduling", {}))
        self.formatter = ContentFormatter(config.get("formatting", {}))

    def initialize_channels(self):
        """Initialize distribution channels"""
        channels = {}

        # Website/Blog
        if "website" in self.config:
            channels["website"] = WebsiteChannel(self.config["website"])

        # Social Media Platforms
        if "social_media" in self.config:
            for platform, config in self.config["social_media"].items():
                channels[f"social_{platform}"] = self.create_social_channel(
                    platform, config
                )

        # Email Newsletter
        if "email" in self.config:
            channels["email"] = EmailChannel(self.config["email"])

        # RSS Feeds
        if "rss" in self.config:
            channels["rss"] = RSSChannel(self.config["rss"])

        # API/Headless
        if "api" in self.config:
            channels["api"] = APIChannel(self.config["api"])

        return channels

    async def distribute_content(
        self, content_id: str, distribution_plan: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute content distribution plan"""

        distribution_result = {
            "content_id": content_id,
            "distribution_id": str(uuid.uuid4()),
            "started_at": datetime.now(timezone.utc),
            "channels": {},
            "overall_status": "in_progress",
        }

        # Get content
        content = await self.get_content(content_id)

        # Process each channel in the distribution plan
        for channel_name, channel_config in distribution_plan.get(
            "channels", {}
        ).items():
            if channel_name not in self.channels:
                distribution_result["channels"][channel_name] = {
                    "status": "error",
                    "error": f"Unknown channel: {channel_name}",
                }
                continue

            try:
                # Format content for the specific channel
                formatted_content = await self.formatter.format_for_channel(
                    content, channel_name, channel_config
                )

                # Schedule or publish immediately
                channel = self.channels[channel_name]

                if channel_config.get("schedule_time"):
                    # Schedule for later
                    schedule_result = await self.scheduler.schedule_distribution(
                        content_id,
                        channel_name,
                        formatted_content,
                        channel_config["schedule_time"],
                    )
                    distribution_result["channels"][channel_name] = {
                        "status": "scheduled",
                        "schedule_time": channel_config["schedule_time"],
                        "schedule_id": schedule_result["schedule_id"],
                    }
                else:
                    # Publish immediately
                    publish_result = await channel.publish(
                        formatted_content, channel_config
                    )
                    distribution_result["channels"][channel_name] = publish_result

            except Exception as e:
                distribution_result["channels"][channel_name] = {
                    "status": "error",
                    "error": str(e),
                }

        # Update overall status
        channel_statuses = [
            result.get("status") for result in distribution_result["channels"].values()
        ]
        if all(status in ["published", "scheduled"] for status in channel_statuses):
            distribution_result["overall_status"] = "completed"
        elif any(status == "error" for status in channel_statuses):
            distribution_result["overall_status"] = "partial"

        distribution_result["completed_at"] = datetime.now(timezone.utc)

        return distribution_result


class ContentFormatter:
    """Format content for different channels"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.templates = self.load_channel_templates()
        self.transformers = self.initialize_transformers()

    async def format_for_channel(
        self, content: Dict[str, Any], channel: str, channel_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Format content for specific channel"""

        formatter_config = self.config.get(channel, {})

        formatted_content = {
            "original": content,
            "channel": channel,
            "formatted_at": datetime.now(timezone.utc),
        }

        # Apply channel-specific transformations
        if channel.startswith("social_"):
            formatted_content = await self.format_for_social_media(
                content, channel.replace("social_", ""), channel_config
            )
        elif channel == "email":
            formatted_content = await self.format_for_email(content, channel_config)
        elif channel == "website":
            formatted_content = await self.format_for_website(content, channel_config)
        elif channel == "api":
            formatted_content = await self.format_for_api(content, channel_config)

        return formatted_content

    async def format_for_social_media(
        self, content: Dict[str, Any], platform: str, config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Format content for social media platforms"""

        platform_limits = {
            "twitter": {"text": 280, "image_count": 4},
            "linkedin": {"text": 3000, "image_count": 1},
            "facebook": {"text": 63206, "image_count": 10},
            "instagram": {"text": 2200, "image_count": 10},
        }

        limits = platform_limits.get(platform, {"text": 500, "image_count": 1})

        # Extract key points for social media
        key_points = self.extract_key_points(content["content"])

        # Create multiple post variations
        post_variations = []

        if platform == "twitter":
            # Twitter thread
            thread = self.create_twitter_thread(content, key_points, limits["text"])
            post_variations.extend(thread)
        else:
            # Single post for other platforms
            post_text = self.create_social_post(content, platform, limits["text"])
            post_variations.append(
                {
                    "text": post_text,
                    "images": content.get("featured_image", [])[
                        : limits["image_count"]
                    ],
                    "hashtags": self.generate_hashtags(content, platform),
                    "link": content.get("canonical_url"),
                }
            )

        return {
            "platform": platform,
            "variations": post_variations,
            "optimal_posting_times": config.get("optimal_times", []),
            "engagement_strategy": config.get("engagement_strategy", {}),
        }

    def create_twitter_thread(
        self, content: Dict[str, Any], key_points: List[str], char_limit: int
    ) -> List[Dict[str, Any]]:
        """Create Twitter thread from content"""

        thread = []

        # First tweet - hook and introduction
        intro_tweet = f"🧵 {content['metadata']['title']}\n\n{content['metadata']['description'][:200]}...\n\nA thread 👇"
        thread.append(
            {
                "text": intro_tweet,
                "tweet_number": 1,
                "images": [content.get("featured_image")]
                if content.get("featured_image")
                else [],
            }
        )

        # Content tweets
        for i, point in enumerate(key_points[:8], 2):  # Max 8 content points
            tweet_text = f"{i}/{len(key_points) + 2} {point}"
            if len(tweet_text) > char_limit:
                tweet_text = tweet_text[: char_limit - 3] + "..."

            thread.append({"text": tweet_text, "tweet_number": i})

        # Final tweet - CTA
        cta_tweet = f"{len(key_points) + 2}/{len(key_points) + 2} Want to dive deeper? Read the full article: {content.get('canonical_url', '')}"
        thread.append({"text": cta_tweet, "tweet_number": len(key_points) + 2})

        return thread
```

## Content Management Output Format

1. **Content Management System**: Complete CMS with versioning, workflows, and multi-channel publishing
1. **Automated Processing Pipeline**: Content validation, transformation, and optimization automation
1. **Localization Management**: Multi-language content workflows with translation automation
1. **SEO Optimization Engine**: Automated SEO analysis and content optimization
1. **Publishing & Distribution**: Multi-channel automated publishing and scheduling
1. **Analytics & Performance Tracking**: Comprehensive content performance monitoring and insights
1. **Workflow Automation**: Configurable content approval and publishing workflows
1. **Quality Assurance**: Automated content validation for accessibility, grammar, and brand compliance
1. **Asset Management**: Automated processing and optimization of images, videos, and documents
1. **Collaboration Tools**: Real-time editing, commenting, and review systems

Focus on creating efficient content workflows that maintain quality while scaling content production across multiple channels and languages, with comprehensive analytics to drive content strategy decisions.

Target: $ARGUMENTS

______________________________________________________________________

## Security Considerations

### Authentication & Authorization

- Implement proper authentication mechanisms for accessing this tool
- Use role-based access control (RBAC) to restrict sensitive operations
- Enable audit logging for all security-relevant actions

### Data Protection

- Encrypt sensitive data at rest and in transit
- Implement proper secrets management (see `secrets-management.md`)
- Follow data minimization principles

### Access Control

- Follow principle of least privilege when granting permissions
- Use dedicated service accounts with minimal required permissions
- Implement multi-factor authentication for production access

### Secure Configuration

- Avoid hardcoding credentials in code or configuration files
- Use environment variables or secure vaults for sensitive configuration
- Regularly rotate credentials and API keys

### Monitoring & Auditing

- Log security-relevant events (authentication, authorization failures, data access)
- Implement alerting for suspicious activities
- Maintain immutable audit trails for compliance

______________________________________________________________________

______________________________________________________________________

## Testing & Validation

### Unit Testing

```python
# Example unit tests
import pytest


def test_basic_functionality():
    result = function_under_test(input_value)
    assert result == expected_output


def test_error_handling():
    with pytest.raises(ValueError):
        function_under_test(invalid_input)


def test_edge_cases():
    assert function_under_test([]) == []
    assert function_under_test(None) is None
```

### Integration Testing

```python
# Integration test example
@pytest.mark.integration
def test_end_to_end_workflow():
    # Setup
    resource = create_resource()

    # Execute workflow
    result = process_resource(resource)

    # Verify
    assert result.status == "success"
    assert result.output is not None

    # Cleanup
    delete_resource(resource.id)
```

### Validation

```bash
# Validate configuration files
yamllint config/*.yaml

# Validate scripts
shellcheck scripts/*.sh

# Run linters
pylint src/
flake8 src/
mypy src/
```

### CI/CD Testing

```yaml
# .github/workflows/test.yml
name: Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - name: Run tests
        run: |
          pytest tests/ -v --cov=src
      - name: Upload coverage
        uses: codecov/codecov-action@v3
```

______________________________________________________________________

______________________________________________________________________

## Troubleshooting

### Common Issues

**Issue 1: Configuration Errors**

**Symptoms:**

- Tool fails to start or execute
- Missing required parameters
- Invalid configuration values

**Solutions:**

1. Verify all required environment variables are set
1. Check configuration file syntax (YAML, JSON)
1. Review logs for specific error messages
1. Validate file paths and permissions

______________________________________________________________________

**Issue 2: Permission Denied Errors**

**Symptoms:**

- Cannot access files or directories
- Operations fail with permission errors
- Insufficient privileges

**Solutions:**

1. Check file/directory permissions: `ls -la`
1. Run with appropriate user privileges
1. Verify user is in required groups: `groups`
1. Use `sudo` for privileged operations when necessary

______________________________________________________________________

**Issue 3: Resource Not Found**

**Symptoms:**

- "File not found" or "Resource not found" errors
- Missing dependencies
- Broken references

**Solutions:**

1. Verify resource paths are correct (use absolute paths)
1. Check that required files exist before execution
1. Ensure dependencies are installed
1. Review environment-specific configurations

______________________________________________________________________

**Issue 4: Timeout or Performance Issues**

**Symptoms:**

- Operations taking longer than expected
- Timeout errors
- Resource exhaustion (CPU, memory, disk)

**Solutions:**

1. Increase timeout values in configuration
1. Optimize queries or operations
1. Add pagination for large datasets
1. Monitor resource usage: `top`, `htop`, `docker stats`
1. Implement caching where appropriate

______________________________________________________________________

### Getting Help

If issues persist after trying these solutions:

1. **Check Logs**: Review application and system logs for detailed error messages
1. **Enable Debug Mode**: Set `LOG_LEVEL=DEBUG` for verbose output
1. **Consult Documentation**: Review related tool documentation in this directory
1. **Contact Support**: Reach out with:
   - Error messages and stack traces
   - Steps to reproduce
   - Environment details (OS, versions, configuration)
   - Relevant log excerpts

______________________________________________________________________
