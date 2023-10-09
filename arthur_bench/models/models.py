from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, validator, root_validator


# COMMON


class ScoringMethodType(str, Enum):
    """
    Indicates whether the scoring method was provided by the package or a custom
    implementation
    """

    BuiltIn = "built_in"
    Custom = "custom"


class ScoringMethod(BaseModel):
    """
    Scoring method configuration
    """

    name: str
    """
    Name of the scorer
    """
    type: ScoringMethodType
    """
    Whether the scoring method was bench default or custom implementation
    """
    config: dict = {}
    """
    Configuration as used by the scorer to_dict and from_dict methods
    """


# REQUESTS


class TestCaseRequest(BaseModel):
    """
    An input, reference output pair.
    """

    input: str
    """
    Input to the test case. Does not include the prompt template.
    """
    reference_output: Optional[str]
    """
    Reference or "Golden" output for the given input.
    """


class TestSuiteRequest(BaseModel):
    """
    Test case data and metadata for the test suite.
    """

    name: str
    """
    Name of the test suite
    """
    description: Optional[str] = None
    """
    Optional description of the test suite
    """
    scoring_method: ScoringMethod
    """
    Scoring configuration to use as criteria for the test suite
    """
    test_cases: List[TestCaseRequest] = Field(..., min_items=1)
    """
    List of input texts and optional reference outputs to consistently score
    model generations against
    """

    @validator("test_cases")
    def null_reference_outputs_all_or_none(cls, v):
        """
        Validate that all or none of test case reference outputs are null
        """
        last_ref_output_null = None
        for tc in v:
            # get ref output value
            if isinstance(tc, TestCaseRequest):
                ref_val = tc.reference_output
            elif isinstance(tc, dict):
                ref_val = tc.get("reference_output", None)
            else:
                raise TypeError(
                    f"Unable to extract reference output value for type '{type(v)}'"
                )

            # check it matches what we've been seeing
            if ref_val is None and last_ref_output_null is False:
                raise ValueError(
                    "Test Suite has both null and non-null reference outputs. Reference"
                    " outputs for test cases within a suite should be all null or all"
                    " non-null."
                )
            if ref_val is not None and last_ref_output_null is True:
                raise ValueError(
                    "Test Suite has both null and non-null reference outputs. Reference"
                    " outputs for test cases within a suite should be all null or all"
                    " non-null."
                )
            if ref_val is None:
                last_ref_output_null = True
            else:
                last_ref_output_null = False

        return v

    @validator("scoring_method", pre=True)
    def scoring_method_backwards_compatible(cls, v):
        if isinstance(v, str):
            return ScoringMethod(name=v, type=ScoringMethodType.BuiltIn)
        return v


class TestCaseOutput(BaseModel):
    """
    A generated output, score pair
    """

    id: UUID
    """
    Optional unique identifier for this test case of the suite and run
    """
    output: str
    """
    Generated output for test case
    """
    score: Optional[float] = None
    """
    Score assigned to output
    """
    label: Optional[str] = None
    """
    Label assigned to output
    """
    reason: Optional[str] = None
    """
    Reason behind the score / label assigned to the output
    """

    @root_validator()
    def either_score_or_label(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        score, label = values.get("score"), values.get("label")
        if not score and not label:
            raise ValueError("Score or a label required for a test case output")
        return values


class CreateRunRequest(BaseModel):
    name: str
    """
    Name identifier of the run
    """
    test_cases: List[TestCaseOutput] = Field(alias="test_case_outputs")
    """
    List of outputs and scores for all cases in the test suite
    """
    description: Optional[str] = None
    """
    Optional description of the run
    """
    model_name: Optional[str] = None
    """
    Optional model name identifying the model used to generate outputs
    """
    foundation_model: Optional[str] = None
    """
    Optional foundation model name identifiying the pretrained model used to generate
    outputs
    """
    prompt_template: Optional[str] = None
    """
    Optional prompt template name identifying the global prompt used to generate outputs
    """
    model_version: Optional[str] = None
    """
    Optional model version identifying the version of the model used to generate outputs
    """

    class Config:
        allow_population_by_field_name = True


# RESPONSES


class TestSuiteMetadata(BaseModel):
    id: UUID
    name: str
    scoring_method: ScoringMethod
    last_run_time: Optional[datetime] = None
    description: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class PaginatedTestSuites(BaseModel):
    """
    Paginated list of test suites.
    """

    test_suites: List[TestSuiteMetadata]
    page: int
    page_size: int
    total_pages: int
    total_count: int


class TestCaseResponse(BaseModel):
    id: UUID
    input: str
    """
    Input to the test case. Does not include the prompt template.
    """
    reference_output: Optional[str] = None
    """
    Reference or "Golden" output for the given input.
    """


class PaginatedTestSuite(BaseModel):
    """
    Test suite and optional page information
    """

    id: UUID
    name: str
    scoring_method: ScoringMethod
    test_cases: List[TestCaseResponse]
    created_at: datetime
    updated_at: datetime
    description: Optional[str] = None
    last_run_time: Optional[datetime] = None
    num_runs: int = 0
    page: Optional[int] = None
    page_size: Optional[int] = None
    total_pages: Optional[int] = None
    total_count: Optional[int] = None


class TestRunMetadata(BaseModel):
    id: UUID
    name: str
    created_at: datetime
    updated_at: datetime
    avg_score: Optional[float] = None
    model_version: Optional[str] = None
    prompt_template: Optional[str] = None


class PaginatedRuns(BaseModel):
    """
    Paginated list of runs for a test suite.
    """

    test_runs: List[TestRunMetadata]
    page: int
    page_size: int
    total_pages: int
    total_count: int


class HistogramItem(BaseModel):
    """
    Boundaries and count for a single bucket of a run histogram
    """

    count: int
    low: Optional[float] = None
    high: Optional[float] = None
    category: Optional[str] = None


class SummaryItem(BaseModel):
    """
    Aggregate statistics for a single run: average score and score distribution
    """

    id: UUID
    name: str
    avg_score: Optional[float]
    histogram: List[HistogramItem]

    @validator("histogram")
    def either_lowhigh_or_category(cls, v):
        """
        Validate that the items in the histogram list are all
        containing low/high floats or are all containing a category
        """
        numerical_histogram = False
        categorical_histogram = False
        both_error = (
            "Histogram has both low/high floats and category "
            "values, which is invalid."
        )
        neither_error = (
            "Histogram item has neither low/high floats nor category "
            "value, which is invalid."
        )
        for h in v:
            if h.low is not None and h.high is not None:
                numerical_histogram = True
                if h.category:
                    raise ValueError(both_error)
            elif h.category:
                categorical_histogram = True
                if h.low or h.high:
                    raise ValueError(both_error)
            else:
                raise ValueError(neither_error)
        if numerical_histogram and categorical_histogram:
            raise ValueError(both_error)
        return v


class TestSuiteSummary(BaseModel):
    """
    Aggregate descriptions of runs of a test suite.
    Provides averages and score distributions
    """

    summary: List[SummaryItem]
    page: int
    page_size: int
    total_pages: int
    total_count: int
    num_test_cases: int


class CreateRunResponse(BaseModel):
    id: UUID


class RunResult(BaseModel):
    id: UUID
    output: str
    score: Optional[float] = None
    label: Optional[str] = None
    reason: Optional[str] = None
    input: Optional[str] = None
    reference_output: Optional[str] = None


class PaginatedRun(BaseModel):
    """
    Paginated list of prompts, reference outputs, model outputs, and scores for a
    particular run.
    """

    id: UUID
    name: str
    test_suite_id: UUID
    test_cases: List[RunResult] = Field(alias="test_case_runs")
    updated_at: datetime
    created_at: datetime
    page: Optional[int] = None
    page_size: Optional[int] = None
    total_pages: Optional[int] = None
    total_count: Optional[int] = None

    class Config:
        allow_population_by_field_name = True
