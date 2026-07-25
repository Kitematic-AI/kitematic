"""Capability catalog — single source of truth for all built-in capabilities."""

from __future__ import annotations

from packaging.version import InvalidVersion, Version

from core.policies.capability import Capability, CapabilityCategory


class CapabilityCatalog:
    """Immutable catalog of all built-in capabilities.

    Use CapabilityCatalog.CHAT_GENERATE.id instead of string literals.
    """

    # Model capabilities
    CHAT_GENERATE = Capability(
        id="chat.generate",
        name="Chat Generation",
        category=CapabilityCategory.MODEL,
        risk_level="low",
        description="Generate chat completions",
    )

    CHAT_STREAM = Capability(
        id="chat.stream",
        name="Chat Streaming",
        category=CapabilityCategory.MODEL,
        risk_level="low",
        description="Stream chat completions",
    )

    EMBEDDING_GENERATE = Capability(
        id="embedding.generate",
        name="Embedding Generation",
        category=CapabilityCategory.MODEL,
        risk_level="low",
        description="Generate text embeddings",
    )

    IMAGE_GENERATE = Capability(
        id="image.generate",
        name="Image Generation",
        category=CapabilityCategory.MEDIA,
        risk_level="medium",
        description="Generate images from prompts",
    )

    IMAGE_EDIT = Capability(
        id="image.edit",
        name="Image Editing",
        category=CapabilityCategory.MEDIA,
        risk_level="medium",
        description="Edit existing images",
    )

    VISION_DETECT = Capability(
        id="vision.detect",
        name="Object Detection",
        category=CapabilityCategory.MEDIA,
        risk_level="medium",
        description="Detect objects in images",
    )

    VISION_CAPTION = Capability(
        id="vision.caption",
        name="Image Captioning",
        category=CapabilityCategory.MEDIA,
        risk_level="low",
        description="Generate image captions",
    )

    SPEECH_TTS = Capability(
        id="speech.tts",
        name="Text-to-Speech",
        category=CapabilityCategory.MEDIA,
        risk_level="low",
        description="Text-to-speech synthesis",
    )

    SPEECH_STT = Capability(
        id="speech.stt",
        name="Speech-to-Text",
        category=CapabilityCategory.MEDIA,
        risk_level="low",
        description="Speech-to-text transcription",
    )

    CODE_GENERATE = Capability(
        id="code.generate",
        name="Code Generation",
        category=CapabilityCategory.CODE,
        risk_level="medium",
        description="Generate source code",
    )

    CODE_REVIEW = Capability(
        id="code.review",
        name="Code Review",
        category=CapabilityCategory.CODE,
        risk_level="medium",
        description="Review source code for issues",
    )

    AGENT_RUN = Capability(
        id="agent.run",
        name="Agent Execution",
        category=CapabilityCategory.MODEL,
        risk_level="medium",
        description="Run autonomous agent loops",
    )

    TOOL_EXECUTE = Capability(
        id="tool.execute",
        name="Tool Execution",
        category=CapabilityCategory.TOOL,
        risk_level="medium",
        description="Execute external tools and APIs",
    )

    FILESYSTEM_READ = Capability(
        id="filesystem.read",
        name="Filesystem Read",
        category=CapabilityCategory.FILESYSTEM,
        risk_level="low",
        description="Read files from filesystem",
    )

    FILESYSTEM_WRITE = Capability(
        id="filesystem.write",
        name="Filesystem Write",
        category=CapabilityCategory.FILESYSTEM,
        risk_level="high",
        description="Write files to filesystem",
    )

    NETWORK_EGRESS = Capability(
        id="network.egress",
        name="Network Egress",
        category=CapabilityCategory.NETWORK,
        risk_level="critical",
        description="Make outbound network requests",
    )

    @classmethod
    def all(cls) -> tuple:
        """Return all registered capabilities as a tuple."""
        return (
            CapabilityCatalog.CHAT_GENERATE,
            CapabilityCatalog.CHAT_STREAM,
            CapabilityCatalog.EMBEDDING_GENERATE,
            CapabilityCatalog.IMAGE_GENERATE,
            CapabilityCatalog.IMAGE_EDIT,
            CapabilityCatalog.VISION_DETECT,
            CapabilityCatalog.VISION_CAPTION,
            CapabilityCatalog.SPEECH_TTS,
            CapabilityCatalog.SPEECH_STT,
            CapabilityCatalog.CODE_GENERATE,
            CapabilityCatalog.CODE_REVIEW,
            CapabilityCatalog.AGENT_RUN,
            CapabilityCatalog.TOOL_EXECUTE,
            CapabilityCatalog.FILESYSTEM_READ,
            CapabilityCatalog.FILESYSTEM_WRITE,
            CapabilityCatalog.NETWORK_EGRESS,
        )

    @classmethod
    def by_id(cls, cap_id: str) -> Capability | None:
        """Look up capability by its string ID."""
        for cap in cls.all():
            if cap.id == cap_id:
                return cap
        return None

    @classmethod
    def resolve_version(cls, cap_id: str, version_constraint: str | None = None) -> Capability | None:
        """Resolve a capability by ID with optional version constraint.

        Args:
            cap_id: The capability ID to look up
            version_constraint: Optional version constraint (exact match in v1)

        Returns:
            Capability if found and matches constraint, None otherwise
        """
        cap = cls.by_id(cap_id)
        if cap is None:
            return None

        if version_constraint is None:
            return cap

        # v1: exact match only
        try:
            constraint_version = Version(version_constraint)
            cap_version = Version(cap.version) if hasattr(cap, 'version') else Version("1.0.0")
            if constraint_version == cap_version:
                return cap
        except InvalidVersion:
            # If version parsing fails, fall back to exact string match
            if hasattr(cap, 'version') and cap.version == version_constraint:
                return cap
        return None

    @classmethod
    def get_compatible(cls, cap_id: str, version_constraint: str | None = None) -> tuple:
        """Get capabilities compatible with the given ID and version constraint.

        Args:
            cap_id: The capability ID to find compatibles for
            version_constraint: Optional version constraint (exact match in v1)

        Returns:
            Tuple of compatible capabilities
        """
        cap = cls.by_id(cap_id)
        if not cap:
            return ()

        if version_constraint is None:
            return (cap,)
        result = cls.resolve_version(cap_id, version_constraint)
        return (result,) if result is not None else ()

    @classmethod
    def query(
        cls,
        category=None,
        risk_level=None,
    ) -> tuple:
        """Query capabilities with optional filters.

        Args:
            category: Filter by capability category
            risk_level: Filter by risk level

        Returns:
            Tuple of matching capabilities
        """
        results = []
        for cap in cls.all():
            if category is not None and cap.category != category:
                continue
            if risk_level is not None and cap.risk_level != risk_level:
                continue
            results.append(cap)
        return tuple(results)
