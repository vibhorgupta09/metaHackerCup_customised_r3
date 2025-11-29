import os
import yaml
import json
import time
from typing import Dict, Optional, Tuple, List, Any
from agents import TesterAgent, BruteAgent, OptimalAgent, SampleExtractorAgent, FinalJudgeAgent
from utils import CodeExecutor, OutputComparator, ProgressIndicator


def load_env_from_file(filename: str = ".env") -> None:
    """Populate os.environ with variables from a simple KEY=VALUE .env file."""
    try:
        with open(filename, "r", encoding="utf-8") as env_file:
            for raw_line in env_file:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and value and key not in os.environ:
                    os.environ[key] = value
    except FileNotFoundError:
        pass
    except OSError:
        pass


load_env_from_file()


class ProblemSolverOrchestrator:
    """Main orchestrator for the multi-agent problem solving system."""

    def __init__(self, config_path: str = "config.yaml"):
        """Initialize orchestrator with configuration."""
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)

        # Set up API keys
        api_keys = self.config.get('api_keys', {})

        google_key = api_keys.get('google')
        if google_key and google_key not in {"your-google-api-key", "your-google-api-key-here"}:
            os.environ['GOOGLE_API_KEY'] = google_key

        openai_key = api_keys.get('openai')
        if openai_key and openai_key != "sk-your-openai-key":
            os.environ['OPENAI_API_KEY'] = openai_key

        # Initialize agents
        self.sample_agent = SampleExtractorAgent(self.config['models']['sample_agent'])
        self.tester_agent = TesterAgent(self.config['models']['tester_agent'])
        self.brute_agent = BruteAgent(self.config['models']['brute_agent'])
        self.optimal_agent = OptimalAgent(self.config['models']['optimal_agent'])
        final_model = self.config['models'].get('final_judge_agent')
        self.final_judge_agent = FinalJudgeAgent(final_model) if final_model else None

        # Initialize utilities
        timeout = self.config['execution']['timeout_seconds']
        self.executor = CodeExecutor(timeout=timeout)
        self.comparator = OutputComparator()

        # Set up workspace
        self.workspace = self.config['output']['workspace_dir']
        os.makedirs(self.workspace, exist_ok=True)

        # File paths
        self.files = {
            'test_inputs': os.path.join(self.workspace, self.config['files']['test_inputs']),
            'brute_solution': os.path.join(self.workspace, self.config['files']['brute_solution']),
            'brute_outputs': os.path.join(self.workspace, self.config['files']['brute_outputs']),
            'optimal_solution': os.path.join(self.workspace, self.config['files']['optimal_solution']),
            'optimal_outputs': os.path.join(self.workspace, self.config['files']['optimal_outputs']),
            'sample_input': os.path.join(self.workspace, 'sample_input.txt'),
            'sample_output': os.path.join(self.workspace, 'sample_output.txt'),
            'sample_run_output': os.path.join(self.workspace, 'sample_run_output.txt')
        }

        self.max_brute_attempts = self.config['execution'].get('max_brute_attempts', 3)
        self.max_attempts = self.config['execution']['max_optimal_attempts']
        self.optimal_temperatures = self.config['execution'].get(
            'optimal_temperatures',
            [0.30, 0.27, 0.24, 0.21, 0.18, 0.15, 0.12, 0.09, 0.06, 0.03]
        )
        self.brute_temperatures = self.config['execution'].get(
            'brute_temperatures',
            [0.25, 0.23, 0.21, 0.19, 0.17, 0.15, 0.13, 0.11, 0.09, 0.07, 0.05, 0.03]
        )
        final_cfg = self.config.get('final_judge', {})
        self.final_judge_enabled = final_cfg.get('enable', False)
        self.final_judge_group_size = final_cfg.get('group_size', 4)

    def solve(self, problem_statement: str) -> Tuple[bool, Optional[str], Dict]:
        """
        Solve the given problem using multi-agent approach.

        Args:
            problem_statement: The problem description

        Returns:
            Tuple of (success, optimal_code, metadata)
        """
        metadata = {
            'attempts': 0,
            'test_cases_generated': False,
            'brute_force_generated': False,
            'brute_force_executed': False,
            'optimal_solution_found': False,
            'errors': [],
            'optimal_attempts': [],  # Store all attempts with details
            'brute_attempts_used': 0,
            'brute_force_attempts': [],
            'sample_cases_available': False,
            'sample_validation_passed': False
        }

        print("=" * 80)
        print("STEP 1: Extracting official sample cases...")
        print("=" * 80)

        try:
            with ProgressIndicator("Extracting sample input"):
                sample_input = self.sample_agent.extract(problem_statement, sample_type='INPUT')
            with ProgressIndicator("Extracting sample output"):
                sample_output = self.sample_agent.extract(problem_statement, sample_type='OUTPUT')

            if not sample_input or not sample_output:
                raise ValueError("Unable to extract both sample input and sample output from problem statement.")

            with open(self.files['sample_input'], 'w') as f_in:
                f_in.write(sample_input.strip() + "\n")
            with open(self.files['sample_output'], 'w') as f_out:
                f_out.write(sample_output.strip() + "\n")

            metadata['sample_cases_available'] = True
            print(f"✓ Sample input saved to: {self.files['sample_input']}")
            print(f"✓ Sample output saved to: {self.files['sample_output']}\n")
        except Exception as e:
            error = f"Failed to extract sample cases: {str(e)}"
            metadata['errors'].append(error)
            print(f"✗ {error}\n")
            return False, None, metadata

        print("=" * 80)
        print("STEP 2: Generating brute force solution (sample validation)...")
        print("=" * 80)

        brute_feedback = None
        brute_success = False
        tests_generated = False

        for brute_attempt in range(1, self.max_brute_attempts + 1):
            metadata['brute_attempts_used'] = brute_attempt
            brute_temp = self.brute_temperatures[(brute_attempt - 1) % len(self.brute_temperatures)]
            print(f"\n--- Brute Force Attempt {brute_attempt}/{self.max_brute_attempts} (temp={brute_temp}) ---")

            brute_attempt_data = {
                'attempt_number': brute_attempt,
                'timestamp': time.time(),
                'code': None,
                'verdict': None,
                'error_message': None,
                'execution_success': False,
                'sample_validation': False,
                'temperature': brute_temp
            }

            try:
                with ProgressIndicator(f"Generating brute force solution (attempt {brute_attempt}/{self.max_brute_attempts}, temp={brute_temp})"):
                    brute_code = self.brute_agent.generate_solution(
                        problem_statement,
                        temperature=brute_temp,
                        feedback=brute_feedback,
                        attempt=brute_attempt
                    )
                brute_attempt_data['code'] = brute_code

                if not self._looks_like_python(brute_code):
                    raise ValueError(
                        "Model response did not look like valid Python code. "
                        "Remember to output ONLY code."
                    )

                attempt_file = os.path.join(self.workspace, f'brute_attempt_{brute_attempt}.py')
                with open(attempt_file, 'w') as f:
                    f.write(brute_code)

                with open(self.files['brute_solution'], 'w') as f:
                    f.write(brute_code)

                metadata['brute_force_generated'] = True
                print(f"✓ Brute force solution saved to: {self.files['brute_solution']}")

            except Exception as e:
                error = f"Failed to generate brute force solution: {str(e)}"
                brute_attempt_data['verdict'] = 'Generation Failed'
                brute_attempt_data['error_message'] = str(e)
                metadata['errors'].append(error)
                metadata['brute_force_attempts'].append(brute_attempt_data)
                brute_feedback = f"Your brute force solution failed to generate:\n{str(e)}\n\nPlease fix the errors."
                print(f"✗ {error}")
                continue

            print("Validating brute force solution on official sample...")

            success, error = self.executor.execute(
                self.files['brute_solution'],
                self.files['sample_input'],
                self.files['sample_run_output']
            )

            if not success:
                error_msg = f"Brute force failed on sample input: {error}"
                brute_attempt_data['verdict'] = 'Runtime Error'
                brute_attempt_data['error_message'] = error
                metadata['errors'].append(error_msg)
                metadata['brute_force_attempts'].append(brute_attempt_data)
                brute_feedback = (
                    "Your brute force solution failed to execute on the official sample input.\n"
                    "You must output ONLY valid Python code with no explanations or Markdown.\n"
                    f"Error details:\n{error}\n\nFix the code so it runs correctly on the sample."
                )
                print(f"✗ {error_msg}\n")
                continue

            with open(self.files['sample_output'], 'r') as f_expected:
                expected_sample_output = f_expected.read().strip()
            with open(self.files['sample_run_output'], 'r') as f_actual:
                actual_sample_output = f_actual.read().strip()

            if expected_sample_output != actual_sample_output:
                diff = (
                    "Sample output mismatch.\n"
                    f"Expected sample output:\n{expected_sample_output}\n\n"
                    f"Actual sample output:\n{actual_sample_output}\n"
                )
                brute_attempt_data['verdict'] = 'Wrong Answer (Sample)'
                brute_attempt_data['error_message'] = diff
                metadata['errors'].append(
                    f"Brute force sample validation failed on attempt {brute_attempt}."
                )
                metadata['brute_force_attempts'].append(brute_attempt_data)
                brute_feedback = (
                    "Your brute force solution does not match the official sample output.\n"
                    f"{diff}\n"
                    "Please fix the logic."
                )
                print(f"✗ Sample output mismatch on attempt {brute_attempt}")
                continue

            brute_attempt_data['sample_validation'] = True
            metadata['sample_validation_passed'] = True
            print("✓ Sample validation passed!\n")

            if not tests_generated:
                print("=" * 80)
                print("STEP 3: Generating edge-case test inputs...")
                print("=" * 80)
                try:
                    with ProgressIndicator("Generating edge-case test cases with TesterAgent"):
                        test_cases = self.tester_agent.generate_test_cases(problem_statement)
                    test_cases = self._normalize_test_cases(test_cases)
                    with open(self.files['test_inputs'], 'w') as f:
                        f.write(test_cases)
                    metadata['test_cases_generated'] = True
                    tests_generated = True
                    print(f"✓ Test cases saved to: {self.files['test_inputs']}\n")
                except Exception as e:
                    error = f"Failed to generate test cases: {str(e)}"
                    brute_attempt_data['verdict'] = 'Test Generation Failed'
                    brute_attempt_data['error_message'] = str(e)
                    metadata['errors'].append(error)
                    metadata['brute_force_attempts'].append(brute_attempt_data)
                    print(f"✗ {error}\n")
                    return False, None, metadata

            print("=" * 80)
            print("STEP 4: Executing brute force solution on generated tests...")
            print("=" * 80)

            success, error = self.executor.execute(
                self.files['brute_solution'],
                self.files['test_inputs'],
                self.files['brute_outputs']
            )

            if not success:
                error_msg = f"Brute force execution failed on generated tests: {error}"
                brute_attempt_data['verdict'] = 'Runtime Error (Generated Tests)'
                brute_attempt_data['error_message'] = error
                metadata['errors'].append(error_msg)
                metadata['brute_force_attempts'].append(brute_attempt_data)
                brute_feedback = (
                    "Your brute force solution failed to execute on the generated edge-case tests.\n"
                    "Carefully handle array bounds, 1-indexed inputs, and ensure lists are sized correctly.\n"
                    f"Error details:\n{error}\n\nFix the issues and try again."
                )
                print(f"✗ {error_msg}\n")
                continue

            metadata['brute_force_attempts'].append(brute_attempt_data)
            brute_attempt_data['execution_success'] = True
            brute_attempt_data['verdict'] = 'Accepted'
            metadata['brute_force_executed'] = True
            brute_success = True
            print(f"✓ Brute force outputs saved to: {self.files['brute_outputs']}\n")
            break

        if not brute_success:
            print(f"\n✗ Failed to produce a working brute force solution in {self.max_brute_attempts} attempts\n")
            return False, None, metadata

        print("=" * 80)
        print("STEP 5: Generating and testing optimal solution...")
        print("=" * 80)

        feedback = None
        optimal_code = None
        final_success_code = None
        success_count = 0

        for attempt in range(1, self.max_attempts + 1):
            metadata['attempts'] = attempt
            temperature = self.optimal_temperatures[(attempt - 1) % len(self.optimal_temperatures)]
            print(f"\n--- Attempt {attempt}/{self.max_attempts} (temp={temperature}) ---")

            attempt_data = {
                'attempt_number': attempt,
                'timestamp': time.time(),
                'code': None,
                'verdict': None,
                'error_message': None,
                'execution_success': False,
                'output_match': False,
                'output_diff': None
            }

            try:
                with ProgressIndicator(f"Generating optimal solution (attempt {attempt}/{self.max_attempts}, temp={temperature})"):
                    optimal_code = self.optimal_agent.generate_solution(
                        problem_statement,
                        temperature=temperature,
                        feedback=feedback,
                        attempt=attempt
                    )

                attempt_data['code'] = optimal_code

                if not self._looks_like_python(optimal_code):
                    raise ValueError(
                        "Model response did not look like valid Python code. "
                        "Remember to output ONLY code."
                    )

                # Save this attempt separately
                attempt_file = os.path.join(self.workspace, f'optimal_attempt_{attempt}.py')
                with open(attempt_file, 'w') as f:
                    f.write(optimal_code)

                # Also update the main optimal solution file
                with open(self.files['optimal_solution'], 'w') as f:
                    f.write(optimal_code)

                print(f"✓ Generated optimal solution")

            except Exception as e:
                error = f"Failed to generate optimal solution: {str(e)}"
                attempt_data['verdict'] = 'Generation Failed'
                attempt_data['error_message'] = str(e)
                metadata['errors'].append(error)
                metadata['optimal_attempts'].append(attempt_data)
                print(f"✗ {error}")
                continue

            # Execute optimal solution
            attempt_output_file = os.path.join(self.workspace, f'optimal_attempt_{attempt}_output.txt')
            success, error = self.executor.execute(
                self.files['optimal_solution'],
                self.files['test_inputs'],
                attempt_output_file
            )

            # Also update main output file
            if success:
                with open(self.files['optimal_outputs'], 'w') as f_out:
                    with open(attempt_output_file, 'r') as f_in:
                        f_out.write(f_in.read())

            if not success:
                print(f"✗ Execution failed: {error}")
                attempt_data['verdict'] = 'Runtime Error'
                attempt_data['error_message'] = error
                attempt_data['execution_success'] = False
                metadata['optimal_attempts'].append(attempt_data)
                feedback = (
                    "Your solution failed to execute.\n"
                    "You must output ONLY valid Python code with no explanations or Markdown.\n"
                    f"Error details:\n{error}\n\nPlease fix the errors."
                )
                metadata['errors'].append(f"Attempt {attempt}: Execution failed - {error}")
                continue

            attempt_data['execution_success'] = True
            print(f"✓ Execution successful")

            # Compare outputs
            if self.comparator.compare(self.files['brute_outputs'], attempt_output_file):
                print(f"✓ Outputs match! Solution found in {attempt} attempt(s)")
                attempt_data['verdict'] = 'Accepted'
                attempt_data['output_match'] = True
                metadata['optimal_attempts'].append(attempt_data)
                metadata['optimal_solution_found'] = True
                print("\n" + "=" * 80)
                print("SUCCESS: Optimal solution found!")
                print("=" * 80)

                # Generate results JSON for viewer
                success_count += 1
                metadata['optimal_solution_found'] = True
                success_file = os.path.join(self.workspace, f'optimal_success_{success_count}.py')
                with open(success_file, 'w') as f:
                    f.write(optimal_code)

                success_output_file = os.path.join(self.workspace, f'optimal_success_{success_count}_output.txt')
                with open(success_output_file, 'w') as f_out, open(attempt_output_file, 'r') as f_in:
                    f_out.write(f_in.read())

                metadata.setdefault('optimal_success_files', []).append(success_file)
                attempt_data['output_match'] = True
                final_success_code = final_success_code or optimal_code
                print(f"✓ Saved accepted solution to: {success_file}")
                continue
            else:
                diff = self.comparator.get_diff_summary(
                    self.files['brute_outputs'],
                    attempt_output_file
                )
                print(f"✗ Outputs don't match")
                print(f"Difference: {diff[:200]}...")
                attempt_data['verdict'] = 'Wrong Answer'
                attempt_data['output_match'] = False
                attempt_data['output_diff'] = diff
                metadata['optimal_attempts'].append(attempt_data)
                feedback = f"Your solution produced incorrect output:\n{diff}\n\nPlease fix the logic."
                metadata['errors'].append(f"Attempt {attempt}: Output mismatch")

        final_judge_summary = None
        if self.final_judge_enabled and self.final_judge_agent:
            final_judge_summary = self._run_final_judge(problem_statement, metadata)
            if final_judge_summary:
                final_success_code = final_success_code or final_judge_summary.get('fallback_code')

        if not metadata['optimal_solution_found']:
            print("\n" + "=" * 80)
            print(f"FAILED: Could not find correct solution in {self.max_attempts} attempts")
            print("=" * 80)
        else:
            print("\n" + "=" * 80)
            print(f"COMPLETED: Found {success_count} accepted solution(s) across {self.max_attempts} attempts")
            print("=" * 80)

        self._generate_results_json(problem_statement, metadata)

        return metadata['optimal_solution_found'], final_success_code or optimal_code, metadata

    @staticmethod
    def _looks_like_python(code: str) -> bool:
        """Heuristic check to ensure response resembles Python code."""
        if not code:
            return False

        stripped = code.lstrip()
        first_line = stripped.splitlines()[0].strip() if stripped.splitlines() else ""

        keywords = ('import ', 'from ', 'def ', 'class ', '#!', '@', 'for ', 'while ', 'if ', 'print(')
        if any(stripped.startswith(k) for k in keywords):
            return True

        if first_line.startswith(("print", "if", "for", "while", "def", "class")):
            return True

        return False

    @staticmethod
    def _normalize_test_cases(test_cases: str) -> str:
        """Remove empty lines to avoid confusing generated parsers."""
        lines = [line for line in test_cases.splitlines() if line.strip()]
        return "\n".join(lines)
    def _generate_results_json(self, problem_statement: str, metadata: Dict):
        """Generate results.json for the web viewer."""
        # Read all necessary files
        test_input = ""
        brute_code = ""
        brute_output = ""
        sample_input = ""
        sample_output = ""

        try:
            with open(self.files['test_inputs'], 'r') as f:
                test_input = f.read()
        except:
            pass

        try:
            with open(self.files['brute_solution'], 'r') as f:
                brute_code = f.read()
        except:
            pass

        try:
            with open(self.files['brute_outputs'], 'r') as f:
                brute_output = f.read()
        except:
            pass

        try:
            with open(self.files['sample_input'], 'r') as f:
                sample_input = f.read()
        except:
            pass

        try:
            with open(self.files['sample_output'], 'r') as f:
                sample_output = f.read()
        except:
            pass

        results = {
            'problem_statement': problem_statement,
            'test_input': test_input,
            'test_output': brute_output,
            'brute_force_code': brute_code,
            'brute_force_attempts': metadata['brute_force_attempts'],
            'optimal_attempts': metadata['optimal_attempts'],
            'success': metadata['optimal_solution_found'],
            'total_attempts': metadata['attempts'],
            'sample_input': sample_input,
            'sample_output': sample_output,
            'sample_validation_passed': metadata.get('sample_validation_passed', False),
            'final_judge': metadata.get('final_judge', {})
        }

        results_file = os.path.join(self.workspace, 'results.json')
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2)

        print(f"\n✓ Results saved to: {results_file}")
        print("\n" + "=" * 80)
        print("📊 VIEW RESULTS IN WEB BROWSER")
        print("=" * 80)
        print("\nTo view the beautiful HTML report, run:")
        print("\n  python -m http.server 8000")
        print("\nThen open: http://localhost:8000/viewer.html")
        print("\n(HTTP server needed to avoid CORS restrictions)")
        print("=" * 80)

    def _run_final_judge(self, problem_statement: str, metadata: Dict) -> Dict[str, Any]:
        candidates = [a for a in metadata['optimal_attempts'] if a.get('code')]
        if len(candidates) < 2 or not self.final_judge_agent:
            return {}

        group_results = []
        winners = []

        def chunk_list(items, size):
            for i in range(0, len(items), size):
                yield items[i:i + max(1, size)]

        for idx, group in enumerate(chunk_list(candidates, self.final_judge_group_size), 1):
            if len(group) == 0:
                continue
            result = self.final_judge_agent.judge(problem_statement, group)
            winner_attempt = self._extract_winner_attempt(result, group)
            winner = self._find_attempt_by_number(group, winner_attempt)
            if not winner:
                winner = group[0]
            winners.append(winner)
            group_results.append({
                'group': idx,
                'candidates': [a['attempt_number'] for a in group],
                'winner_attempt': winner['attempt_number'],
                'reason': result.get('reason') if isinstance(result, dict) else None
            })

        final_summary = {
            'group_results': group_results,
            'top_winner_attempts': [],
            'comparator_file': None,
            'fallback_code': None
        }

        if not winners:
            metadata['final_judge'] = final_summary
            return final_summary

        top_winners = winners[:4]
        comparator_path = os.path.join(self.workspace, 'final_comparator.txt')
        with open(comparator_path, 'w') as f:
            f.write("Problem Statement:\n")
            f.write(problem_statement.strip() + "\n\n")
            for idx, winner in enumerate(top_winners, 1):
                f.write(f"Winner {idx} (Attempt {winner['attempt_number']}):\n")
                f.write(f"Verdict: {winner.get('verdict')}\n")
                f.write(f"Output match: {winner.get('output_match')}\n")
                f.write(f"Execution success: {winner.get('execution_success')}\n")
                f.write(f"Notes: {winner.get('error_message') or 'N/A'}\n")
                f.write("Code:\n")
                f.write((winner.get('code') or "").strip())
                f.write("\n\n")

        final_summary.update({
            'top_winner_attempts': [w['attempt_number'] for w in top_winners],
            'comparator_file': comparator_path,
            'fallback_code': top_winners[0]['code'] if top_winners else None
        })

        metadata['final_judge'] = final_summary
        print("\n" + "=" * 80)
        print(f"FINAL JUDGE: Prepared comparator file with {len(top_winners)} candidate(s) at {comparator_path}")
        print("=" * 80)
        return final_summary

    @staticmethod
    def _extract_winner_attempt(result: Dict[str, Any], candidates: List[Dict[str, Any]]) -> Optional[int]:
        if not isinstance(result, dict):
            return None
        winner = result.get('winner_attempt')
        if isinstance(winner, str):
            winner = ''.join(ch for ch in winner if ch.isdigit())
        try:
            winner = int(winner)
        except (TypeError, ValueError):
            winner = None
        if winner is None:
            accepted = [c['attempt_number'] for c in candidates if c.get('output_match')]
            return accepted[0] if accepted else candidates[0]['attempt_number']
        return winner

    @staticmethod
    def _find_attempt_by_number(candidates: List[Dict[str, Any]], attempt_number: Optional[int]) -> Optional[Dict[str, Any]]:
        for candidate in candidates:
            if candidate.get('attempt_number') == attempt_number:
                return candidate
        return None
