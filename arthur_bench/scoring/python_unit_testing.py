# flake8: noqa
from evaluate import load
import os

os.environ[
    "HF_ALLOW_CODE_EVAL"
] = "1"  # required for executing code using the HuggingFace code_eval metric
from typing import List, Optional, Union
from tqdm import tqdm

from arthur_bench.exceptions import UserValueError
from arthur_bench.scoring import Scorer, Feedback
from arthur_bench.scoring.scorer import SINGLE_ITEM_BATCH_DEFAULT

pass_fail_map = {0.0: "fail", 1.0: "pass"}


class PythonUnitTesting(Scorer):
    """
    Wrapping the HuggingFace code_eval metric

    Scores each candidate_output as a function against a pre-prepared unit test

    Note: considers any code with non-standard python libraries (e.g. numpy) to have an
    error

    https://huggingface.co/spaces/evaluate-metric/code_eval
    """

    def __init__(
        self,
        unit_test_dir: Optional[str] = None,
        unit_tests: Optional[List[str]] = None,
    ):
        self.evaluator = load("code_eval")  # type: ignore
        if unit_test_dir is not None:
            try:
                self.unit_tests = [
                    open(f"{unit_test_dir}/{x}").read()
                    for x in sorted(os.listdir(unit_test_dir))
                ]
            except FileNotFoundError as e:
                raise UserValueError(
                    f"Unable to read unit test files from unit_test_dir "
                    f"{unit_test_dir}: "
                ) from e
        else:
            if unit_tests is None:
                raise ValueError(
                    "Must create a PythonUnitTesting scoring method with either a "
                    "unit_test_dir parameter (to read unit tests from a file)"
                    " or a unit_tests parameter directly (to read unit tests as a list "
                    "of strings)"
                )
            self.unit_tests = unit_tests

    @staticmethod
    def name() -> str:
        return "python_unit_testing"

    @staticmethod
    def requires_reference() -> bool:
        return False

    def to_dict(self, warn=False):
        return {"unit_tests": self.unit_tests, "possible_values" : ["pass", "fail"]}

    def run(
        self,
        candidate_outputs: List[str],
        reference_outputs: Optional[List[str]] = None,
        inputs: Optional[List[str]] = None,
        contexts: Optional[List[str]] = None,
        batch_size: int = SINGLE_ITEM_BATCH_DEFAULT,
    ) -> List[Feedback]:
        res = []
        for i in tqdm(range(len(candidate_outputs))):
            pass_at_k, _ = self.evaluator.compute(
                references=[self.unit_tests[i]], predictions=[[candidate_outputs[i]]]
            )
            res.append(Feedback(label=pass_fail_map[pass_at_k["pass@1"]]))
        return res

    def run_batch(
        self,
        candidate_batch: List[str],
        reference_batch: Optional[List[str]] = None,
        input_text_batch: Optional[List[str]] = None,
        context_batch: Optional[List[str]] = None,
    ) -> List[Feedback]:
        raise NotImplementedError(
            "run_batch is not implemented for this scorer. "
            "Use PythonUnitTesting.run(candidates) instead."
        )
