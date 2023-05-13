#!/usr/bin/env python3
import os
import json
import random
from typing import Dict, List, Tuple

from helm.common.general import ensure_file_downloaded
from .scenario import (
    Scenario,
    Instance,
    Reference,
    TEST_SPLIT,
    CORRECT_TAG,
    PassageQuestionInput,
    Input,
    Output,
)


class VerifiabilityJudgementScenario(Scenario):
    """
    The verifiability judgement dataset is from the paper:
    https://arxiv.org/abs/2304.09848

    Original repository can be found at:
    https://github.com/nelson-liu/evaluating-verifiability-in-generative-search-engines

    Given (1) a statement generated by a language model and (2) a cited source,
    the goal is to predict whether the source "fully supports", "partially supports", or
    "does not support" the generated statement.
    The judgments in the dataset are created by crowd sourced human annotators.
    For more details, see https://arxiv.org/abs/2304.09848.

    More concretely, we prompt models using the following format

        Given the statement and its source, judge whether the source "fully supports",
        "partially supports" or "does not support" the statement.

        Statement: <statement>
        Source: <source text>

    The judgement contains both the predicted label (one of "fully supports",
    "partially supports" or "does not support") and an explanation. We extract
    the the predicted label and compare it to the reference in the metric.

    Using an example from the training dataset, we have:

    ```
    Given the statement and its source, judge whether the source "fully supports",
    "partially supports" or "does not support" the statement.

    When providing your judgement, use the following template to list all the relevant
    known and implied information:
    "It is directly known that 1) ... 2) ... It is inferrable that 1)... 2)...
    So the overall the answer is ... because ..."

    Statement: However, many schools are adding more plant-based options to their menus.
    Source: Options are growing for students looking for vegan and vegetarian meals ...
    Bradley said. “Having these options allows us to serve those students and families who —
    whether it’s a dietary preference or religious beliefs — we have options that they
    can eat at school.”
    Judgement:
    ```

    References

    ```
    ['fully supports']
    ```
    """

    name = "verifiability_judgment"
    description = "Verifying whether a statement is fully, partially, or not supported by a given source."
    tags = ["verifiability"]
    _labels_to_targets = {
        "complete_support": "fully supports",
        "partial_support": "partially supports",
        "no_support": "does not support",
    }

    def __init__(self):
        super().__init__()

    def process_example(self, sample: dict) -> Tuple[Input, List[str]]:
        """
        Given an sample from the dataset, create the prompt and the list of
        correct references.
        """
        source_texts = []
        # Add the title, byline, and date if they exist
        if (sample.get("source_title") or "").strip():
            source_texts.append(sample["source_title"])
        if (sample.get("source_author") or "").strip():
            source_texts.append(sample["source_author"])
        if (sample.get("source_date") or "").strip():
            source_texts.append(sample["source_date"])
        source_texts.extend(sample["source_text"])
        source_text = " ".join(source_texts)

        statement = sample["statement"]
        prompt = PassageQuestionInput(
            passage=statement, separator="\n\n", question_prefix="Source: ", question=source_text
        )

        answers: List[str] = [self._labels_to_targets[sample["source_supports_statement"]]]
        return prompt, answers

    def get_file_instances(self, target_file: str, split: str) -> List[Instance]:
        """
        Helper for generating instances for a split.
        Args:
            target_file (str): Data file.
            split (str): Which splits to partition the data into.
        Returns:
            List[Instance]: Instances from the file for the specified split.
        """
        all_samples: List[Dict] = []
        with open(target_file, encoding="utf-8") as f:
            for line in f:
                all_samples.append(json.loads(line))

        file_instances: List[Instance] = []
        for sample in all_samples:
            prompt, answers = self.process_example(sample)
            instance = Instance(
                input=prompt,
                references=[Reference(Output(text=answer), tags=[CORRECT_TAG]) for answer in answers],
                split=split,
            )
            file_instances.append(instance)
        return file_instances

    def get_instances(self) -> List[Instance]:
        data_path: str = os.path.join(self.output_path, "data")
        data_url: str = (
            "https://github.com/nelson-liu/evaluating-verifiability-in-generative-search-engines/"
            "raw/main/verifiability_judgments.jsonl.tar.gz")
        verifiability_path: str = os.path.join(data_path, "verifiability_judgments.jsonl")
        ensure_file_downloaded(
            source_url=data_url,
            target_path=verifiability_path,
            unpack=True)
        assert os.path.exists(verifiability_path)
        random.seed(0)  # randomness needed to pick question at random
        instances: List[Instance] = self.get_file_instances(target_file=verifiability_path, split=TEST_SPLIT)
        return instances
