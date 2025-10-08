"""
Schema validation utilities for EduGPT-PersonalisedLearning.

Provides robust JSON Schema validation with clear error messages and
automatic repair suggestions for common validation failures.

Production features:
- Format validation (URI, datetime)
- Deep copy to prevent mutations
- Type coercion (strings to numbers)
- Removal of unknown keys
- Unique ID and acyclic prerequisite checks
- Transparent repair tracking
- Configurable workload buffer
"""

import json
import re
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import jsonschema
from jsonschema import Draft7Validator, FormatChecker, ValidationError


class ValidationResult:
    """
    Result of a validation attempt.

    Attributes:
        valid: Whether data passed validation
        errors: List of error messages
        data: The validated data (may be modified if repair was attempted)
        repairs: List of repairs applied (for transparency)
    """

    def __init__(
        self,
        valid: bool,
        errors: list[str],
        data: Any = None,
        repairs: Optional[list[str]] = None,
    ):
        self.valid = valid
        self.errors = errors
        self.data = data
        self.repairs = repairs or []

    def __bool__(self) -> bool:
        """Allow using result in boolean context."""
        return self.valid

    def __str__(self) -> str:
        """Human-readable representation."""
        if self.valid:
            msg = "✓ Validation passed"
            if self.repairs:
                msg += f" (with {len(self.repairs)} repair(s))"
            return msg
        return f"✗ Validation failed with {len(self.errors)} error(s):\n" + "\n".join(
            f"  - {error}" for error in self.errors
        )


class SchemaValidator:
    """
    JSON Schema validator with auto-repair capabilities.

    Usage:
        validator = SchemaValidator("path/to/schema.json")
        result = validator.validate(data)
        if result:
            print("Valid!")
            print("Repairs applied:", result.repairs)
        else:
            print(result.errors)
    """

    def __init__(self, schema_path: Path | str):
        """
        Initialize validator with a schema file.

        Args:
            schema_path: Path to JSON Schema file
        """
        self.schema_path = Path(schema_path)
        with open(self.schema_path, "r") as f:
            self.schema = json.load(f)
        # Use FormatChecker to validate URI, datetime, etc.
        self.validator = Draft7Validator(self.schema, format_checker=FormatChecker())

    def validate(
        self, data: dict, auto_repair: bool = False
    ) -> ValidationResult:
        """
        Validate data against schema.

        Args:
            data: Data to validate
            auto_repair: If True, attempt to fix common validation errors

        Returns:
            ValidationResult with validation status and any errors
        """
        errors = []

        # Collect all validation errors
        for error in self.validator.iter_errors(data):
            errors.append(self._format_error(error))

        if errors:
            if auto_repair:
                # Attempt to repair common issues
                repaired_data, repairs = self._attempt_repair(data, errors)
                # Re-validate repaired data
                result = self.validate(repaired_data, auto_repair=False)
                result.repairs = repairs  # Attach repair history
                return result
            return ValidationResult(valid=False, errors=errors, data=data)

        return ValidationResult(valid=True, errors=[], data=data)

    def _format_error(self, error: ValidationError) -> str:
        """
        Convert ValidationError to human-readable message with details.

        Args:
            error: jsonschema ValidationError

        Returns:
            Formatted error message with validator and schema path
        """
        path = " -> ".join(str(p) for p in error.path) if error.path else "root"
        validator_name = getattr(error, "validator", "unknown")
        schema_path = "/".join(str(p) for p in error.schema_path)
        return (
            f"At '{path}': {error.message} "
            f"[validator={validator_name}, schema_path=/{schema_path}]"
        )

    def _attempt_repair(
        self, data: dict, errors: list[str]
    ) -> tuple[dict, list[str]]:
        """
        Attempt to automatically fix common validation errors.

        Args:
            data: Original data
            errors: List of validation errors

        Returns:
            Tuple of (repaired data, list of repairs applied)
        """
        # Deep copy to prevent mutation of original
        repaired = deepcopy(data)
        repairs = []

        # Strip unknown keys (additionalProperties: false)
        self._strip_additional_props(repaired, self.schema, repairs)

        # Coerce common types (strings to numbers)
        self._coerce_types(repaired, repairs)

        # Add missing meta.schema_version
        if "meta" not in repaired:
            repaired["meta"] = {}
            repairs.append("Created missing 'meta' object")
        if "schema_version" not in repaired.get("meta", {}):
            repaired["meta"]["schema_version"] = 1
            repairs.append("Added meta.schema_version = 1")

        # Add missing meta.created_at
        if "created_at" not in repaired.get("meta", {}):
            from datetime import timezone
            timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            repaired["meta"]["created_at"] = timestamp
            repairs.append(f"Added meta.created_at = {timestamp}")

        # Calculate total_estimated_hours if missing
        if "modules" in repaired and "total_estimated_hours" not in repaired:
            total_hours = sum(
                module.get("estimated_hours", 0) for module in repaired["modules"]
            )
            repaired["total_estimated_hours"] = total_hours
            repairs.append(f"Calculated total_estimated_hours = {total_hours}")

        # Calculate workload_feasible if missing (using buffer ratio if available)
        if all(
            key in repaired
            for key in ["total_estimated_hours", "duration_weeks", "weekly_time_hours"]
        ):
            hours_per_week = (
                repaired["total_estimated_hours"] / repaired["duration_weeks"]
            )
            buffer = getattr(self, "buffer_ratio", 0.0)
            feasible = hours_per_week <= (repaired["weekly_time_hours"] * (1 + buffer))
            repaired["workload_feasible"] = feasible
            repairs.append(f"Calculated workload_feasible = {feasible}")

        # Fix module IDs to match pattern (m01-topic-name)
        if "modules" in repaired:
            for i, module in enumerate(repaired["modules"], start=1):
                if "id" not in module or not self._is_valid_module_id(module["id"]):
                    # Generate valid ID from title
                    title_slug = self._slugify(module.get("title", f"module-{i}"))
                    new_id = f"m{i:02d}-{title_slug}"
                    module["id"] = new_id
                    repairs.append(f"Generated module ID: {new_id}")

        # Enforce HTTPS for resource URLs
        if "modules" in repaired:
            for module in repaired["modules"]:
                for resource in module.get("resources", []) or []:
                    url = resource.get("url")
                    if isinstance(url, str) and url.startswith("http://"):
                        https_url = "https://" + url[len("http://") :]
                        resource["url"] = https_url
                        repairs.append(f"Upgraded HTTP to HTTPS: {https_url}")

        return repaired, repairs

    def _strip_additional_props(
        self, obj: Any, schema: dict, repairs: list[str], path: str = "root"
    ):
        """
        Recursively remove keys not allowed by schema (additionalProperties: false).
        Handles both objects and arrays.

        Args:
            obj: Object to strip (dict or list)
            schema: Schema definition
            repairs: List to append repair messages
            path: Current path (for repair messages)
        """
        if not isinstance(schema, dict):
            return

        # Handle objects (dicts)
        if isinstance(obj, dict) and "properties" in schema:
            allowed = set(schema.get("properties", {}).keys())
            if schema.get("additionalProperties") is False:
                extra_keys = [k for k in list(obj.keys()) if k not in allowed]
                for k in extra_keys:
                    obj.pop(k, None)
                    repairs.append(f"Removed unknown key '{k}' at {path}")

            # Recurse into nested objects
            for k, subschema in schema.get("properties", {}).items():
                if k in obj:
                    new_path = f"{path}.{k}"
                    self._strip_additional_props(obj[k], subschema, repairs, new_path)

        # Handle arrays (lists)
        if isinstance(obj, list) and "items" in schema:
            item_schema = schema["items"]
            for i, item in enumerate(obj):
                self._strip_additional_props(
                    item, item_schema, repairs, f"{path}[{i}]"
                )

    def _coerce_types(self, data: dict, repairs: list[str]):
        """
        Coerce common type mismatches (e.g., string "5.0" → number 5.0).

        Args:
            data: Data to coerce
            repairs: List to append repair messages
        """

        def safe_float(x):
            try:
                return float(x)
            except (ValueError, TypeError):
                return x

        def safe_int(x):
            try:
                return int(float(x))
            except (ValueError, TypeError):
                return x

        # Coerce weekly_time_hours
        wth = data.get("weekly_time_hours")
        if isinstance(wth, str):
            coerced = safe_float(wth)
            if coerced != wth:
                data["weekly_time_hours"] = coerced
                repairs.append(f"Coerced weekly_time_hours: '{wth}' → {coerced}")

        # Coerce duration_weeks
        dw = data.get("duration_weeks")
        if isinstance(dw, str):
            coerced = safe_int(dw)
            if coerced != dw:
                data["duration_weeks"] = coerced
                repairs.append(f"Coerced duration_weeks: '{dw}' → {coerced}")

        # Coerce module estimated_hours and assessment passing_threshold
        for i, module in enumerate(data.get("modules", []), start=1):
            eh = module.get("estimated_hours")
            if isinstance(eh, str):
                coerced = safe_float(eh)
                if coerced != eh:
                    module["estimated_hours"] = coerced
                    repairs.append(
                        f"Coerced module {i} estimated_hours: '{eh}' → {coerced}"
                    )

            # Coerce assessment.passing_threshold
            assessment = module.get("assessment", {})
            if isinstance(assessment, dict):
                pt = assessment.get("passing_threshold")
                if isinstance(pt, str):
                    coerced = safe_float(pt)
                    if coerced != pt:
                        assessment["passing_threshold"] = coerced
                        repairs.append(
                            f"Coerced module {i} passing_threshold: '{pt}' → {coerced}"
                        )

    def _is_valid_module_id(self, module_id: str) -> bool:
        """Check if module ID matches required pattern."""
        return bool(re.match(r"^m[0-9]{2}-[a-z0-9-]+$", module_id))

    def _slugify(self, text: str) -> str:
        """
        Convert text to URL-friendly slug.

        Args:
            text: Input text

        Returns:
            Slugified text (lowercase, hyphens, alphanumeric)
        """
        # Lowercase and replace spaces with hyphens
        slug = text.lower().strip()
        slug = re.sub(r"[^\w\s-]", "", slug)
        slug = re.sub(r"[-\s]+", "-", slug)
        return slug[:50]  # Limit length


class SyllabusValidator(SchemaValidator):
    """
    Specialized validator for syllabus documents.

    Adds domain-specific validation beyond JSON Schema:
    - Workload feasibility checks (with configurable buffer)
    - Prerequisite validation
    - Module uniqueness
    - Acyclic prerequisite graph
    - Topological sorting
    """

    def __init__(
        self,
        schema_path: Optional[Path] = None,
        buffer_ratio: Optional[float] = None,
    ):
        """
        Initialize syllabus validator.

        Args:
            schema_path: Path to schema (uses default if None)
            buffer_ratio: Workload buffer ratio (default: 0.10 for 10%)
        """
        if schema_path is None:
            # Use absolute import for better compatibility
            from pathlib import Path as P

            # Try to import config, fallback to default path
            try:
                from config import config

                schema_path = config.paths.syllabus_schema
            except ImportError:
                # Fallback to default location
                project_root = P(__file__).parent.parent.parent
                schema_path = project_root / "schemas" / "syllabus.schema.json"

        super().__init__(schema_path)
        self.buffer_ratio = buffer_ratio if buffer_ratio is not None else 0.10

    def validate(self, data: dict, auto_repair: bool = True) -> ValidationResult:
        """
        Validate syllabus with domain-specific checks.

        Args:
            data: Syllabus data to validate
            auto_repair: Whether to attempt automatic repairs

        Returns:
            ValidationResult
        """
        # First, run standard schema validation
        result = super().validate(data, auto_repair=auto_repair)

        if not result.valid:
            return result

        # Additional domain-specific validations
        errors = []
        validated_data = result.data

        modules = validated_data.get("modules", [])

        # Check unique module IDs
        duplicate_ids = self._find_duplicate_ids(modules)
        if duplicate_ids:
            dups_str = ", ".join(sorted(duplicate_ids))
            errors.append(f"Duplicate module IDs found: {dups_str} (IDs must be unique)")

        # Check prerequisite graph is acyclic and optionally sort
        acyclic, sorted_modules = self._check_acyclic_and_toposort(modules)
        if not acyclic:
            errors.append("Prerequisite graph has a cycle (modules form a loop)")
        else:
            # Enforce topological order so delivery respects prereqs
            validated_data["modules"] = sorted_modules
            if sorted_modules != modules:
                result.repairs.append("Reordered modules in topological order")

        # Check workload feasibility
        if not self._check_workload_feasible(validated_data):
            hours_per_week = (
                validated_data.get("total_estimated_hours", 0)
                / validated_data.get("duration_weeks", 1)
            )
            budget = validated_data.get("weekly_time_hours", 0)
            errors.append(
                f"Workload not feasible: {hours_per_week:.1f} hrs/week exceeds "
                f"budget of {budget} hrs/week (with {self.buffer_ratio*100:.0f}% buffer)"
            )

        # Check prerequisite references
        prereq_errors = self._check_prerequisites(validated_data)
        errors.extend(prereq_errors)

        if errors:
            return ValidationResult(
                valid=False, errors=errors, data=validated_data, repairs=result.repairs
            )

        return ValidationResult(
            valid=True, errors=[], data=validated_data, repairs=result.repairs
        )

    def _check_workload_feasible(self, data: dict) -> bool:
        """
        Verify that total workload fits within weekly time budget.

        Args:
            data: Syllabus data

        Returns:
            True if workload is feasible
        """
        total_hours = data.get("total_estimated_hours", 0)
        duration_weeks = data.get("duration_weeks", 1)
        weekly_budget = data.get("weekly_time_hours", 0)

        if duration_weeks == 0:
            return False

        hours_per_week = total_hours / duration_weeks
        return hours_per_week <= weekly_budget * (1 + self.buffer_ratio)

    def _check_prerequisites(self, data: dict) -> list[str]:
        """
        Validate that all prerequisite references point to valid modules.
        Also checks for self-prerequisites.

        Args:
            data: Syllabus data

        Returns:
            List of error messages (empty if valid)
        """
        errors = []
        modules = data.get("modules", [])
        module_ids = {module["id"] for module in modules}

        for module in modules:
            prereqs = module.get("prerequisites", [])
            for prereq_id in prereqs:
                # Check for self-prerequisite
                if prereq_id == module["id"]:
                    errors.append(
                        f"Module '{module['id']}' lists itself as a prerequisite"
                    )
                # Check for unknown prerequisite
                elif prereq_id not in module_ids:
                    errors.append(
                        f"Module '{module['id']}' references unknown prerequisite '{prereq_id}'"
                    )

        return errors

    def _find_duplicate_ids(self, modules: list[dict]) -> set[str]:
        """
        Find duplicate module IDs using O(n) Counter approach.

        Args:
            modules: List of module dicts

        Returns:
            Set of duplicate IDs (empty if all unique)
        """
        from collections import Counter

        counts = Counter(m["id"] for m in modules)
        return {i for i, c in counts.items() if c > 1}

    def _check_acyclic_and_toposort(
        self, modules: list[dict]
    ) -> tuple[bool, list[dict]]:
        """
        Check if prerequisite graph is acyclic and return topologically sorted modules.

        Uses Kahn's algorithm for topological sorting with deterministic ordering
        (multiple nodes with indegree 0 are processed in sorted order).

        Args:
            modules: List of module dicts

        Returns:
            Tuple of (is_acyclic, sorted_modules)
        """
        if not modules:
            return True, []

        import bisect

        id_to_mod = {m["id"]: m for m in modules}
        indeg = {m["id"]: 0 for m in modules}

        # Build reverse edges: prerequisite -> dependents
        rev = {m["id"]: set() for m in modules}
        for m in modules:
            for p in m.get("prerequisites", []) or []:
                if p in rev:  # Only count valid prereqs
                    indeg[m["id"]] += 1
                    rev[p].add(m["id"])

        # Kahn's algorithm with deterministic ordering
        queue = sorted([i for i, d in indeg.items() if d == 0])
        order = []

        while queue:
            n = queue.pop(0)
            order.append(n)
            for dep in sorted(rev[n]):  # Process dependents in sorted order
                indeg[dep] -= 1
                if indeg[dep] == 0:
                    # Maintain sorted insertion for determinism
                    bisect.insort(queue, dep)

        acyclic = len(order) == len(modules)
        sorted_modules = [id_to_mod[i] for i in order] if acyclic else modules

        return acyclic, sorted_modules


# Convenience function for quick validation
def validate_syllabus(data: dict, auto_repair: bool = True) -> ValidationResult:
    """
    Quick validation of syllabus data.

    Args:
        data: Syllabus dictionary to validate
        auto_repair: Whether to attempt automatic repairs

    Returns:
        ValidationResult

    Example:
        result = validate_syllabus(syllabus_dict)
        if result:
            print("Valid syllabus!")
            print("Repairs:", result.repairs)
        else:
            print("Errors:", result.errors)
    """
    validator = SyllabusValidator()
    return validator.validate(data, auto_repair=auto_repair)
