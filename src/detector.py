import os
import json
from pathlib import Path
from typing import Dict, Any


class LanguageDetector:
    """Detects the primary language and framework of a project."""

    def __init__(self):
        # Define indicators for different languages
        self.indicators = {
            'python': {
                'files': ['requirements.txt', 'setup.py', 'pyproject.toml', 'Pipfile', 'environment.yml'],
                'frameworks': {
                    'flask': ['flask'],
                    'django': ['django'],
                    'fastapi': ['fastapi'],
                    'streamlit': ['streamlit'],
                }
            },
            'nodejs': {
                'files': ['package.json', 'yarn.lock', 'package-lock.json'],
                'frameworks': {
                    'express': ['express'],
                    'next': ['next'],
                    'nuxt': ['nuxt'],
                    'nest': ['@nestjs/core'],
                    'react': ['react'],
                    'vue': ['vue'],
                    'angular': ['@angular/core'],
                    'svelte': ['svelte'],
                    'vite': ['vite'],
                }
            }
        }

    def detect(self, repo_path: Path) -> Dict[str, Any]:
        """
        Detect the language and framework of the repository.

        Args:
            repo_path (Path): Path to the cloned repository.

        Returns:
            dict: Information about the detected language and framework.
                  Example: {'language': 'python', 'framework': 'flask', 'confidence': 0.9}
        """
        # Initialize result
        result = {
            'language': 'unknown',
            'framework': None,
            'confidence': 0.0,
            'details': {}
        }

        # Check for each language
        for language, config in self.indicators.items():
            confidence = 0.0
            details = {}

            # Check for indicator files
            for indicator_file in config['files']:
                if (repo_path / indicator_file).exists():
                    confidence += 0.4  # Each file adds confidence
                    details[f'found_{indicator_file}'] = True

            # If we found at least one indicator file, check for frameworks
            if confidence > 0:
                # Try to read package.json or requirements.txt to find dependencies
                dependencies = self._get_dependencies(repo_path, language)
                details['dependencies'] = dependencies

                # Check for frameworks in dependencies
                for framework, indicators in config['frameworks'].items():
                    for indicator in indicators:
                        # Case-insensitive match for framework detection
                        for dep_name in dependencies:
                            if indicator.lower() == dep_name.lower():
                                confidence += 0.4  # Framework found adds more confidence
                                result['framework'] = framework
                                break
                        if result['framework']:
                            break
                    if result['framework']:
                        break

                # If no specific framework found, set to None but keep language
                if not result['framework']:
                    result['framework'] = 'unknown'

            # Update result if this language has higher confidence
            if confidence > result['confidence']:
                result['language'] = language
                result['confidence'] = min(confidence, 1.0)  # Cap at 1.0
                result['details'] = details

        # If no language detected, try to infer from file extensions
        if result['language'] == 'unknown':
            result = self._infer_from_extensions(repo_path, result)

        return result

    def _get_dependencies(self, repo_path: Path, language: str) -> Dict[str, str]:
        """
        Extract dependencies from the project's manifest file.

        Args:
            repo_path (Path): Path to the repository.
            language (str): The language to get dependencies for.

        Returns:
            dict: A dictionary of dependency names and versions.
        """
        dependencies = {}
        try:
            if language == 'nodejs':
                package_json = repo_path / 'package.json'
                if package_json.exists():
                    with open(package_json, 'r') as f:
                        data = json.load(f)
                        # Combine dependencies and devDependencies
                        deps = data.get('dependencies', {})
                        dev_deps = data.get('devDependencies', {})
                        dependencies = {**deps, **dev_deps}
            elif language == 'python':
                # Try requirements.txt first
                req_txt = repo_path / 'requirements.txt'
                if req_txt.exists():
                    with open(req_txt, 'r') as f:
                        for line in f:
                            line = line.strip()
                            if line and not line.startswith('#'):
                                # Extract package name (ignore version specifiers for simplicity)
                                pkg = line.split('==')[0].split('>=')[0].split('<=')[0].split('!=')[0].strip()
                                if pkg:
                                    dependencies[pkg] = 'unknown'  # We don't capture version here for simplicity
                # Could also check Pipfile, pyproject.toml, etc. but for MVP we keep it simple
        except Exception as e:
            # If we can't read the file, just return empty dependencies
            pass
        return dependencies

    def _infer_from_extensions(self, repo_path: Path, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Infer language from file extensions when no manifest files are found.

        Args:
            repo_path (Path): Path to the repository.
            result (dict): Current result dictionary to update.

        Returns:
            dict: Updated result dictionary.
        """
        # Count file extensions
        extension_counts = {}
        for file_path in repo_path.rglob('*'):
            if file_path.is_file():
                ext = file_path.suffix.lower()
                if ext:
                    extension_counts[ext] = extension_counts.get(ext, 0) + 1

        # Map extensions to languages
        ext_to_lang = {
            '.py': 'python',
            '.js': 'nodejs',
            '.ts': 'nodejs',
            '.jsx': 'nodejs',
            '.tsx': 'nodejs',
            '.html': 'unknown',  # Could be any, but often frontend
            '.css': 'unknown',
        }

        # Find the most common extension that maps to a known language
        lang_scores = {}
        for ext, count in extension_counts.items():
            if ext in ext_to_lang:
                lang = ext_to_lang[ext]
                lang_scores[lang] = lang_scores.get(lang, 0) + count

        if lang_scores:
            # Get the language with the highest score
            detected_lang = max(lang_scores, key=lang_scores.get)
            total_files = sum(extension_counts.values())
            confidence = lang_scores[detected_lang] / total_files if total_files > 0 else 0
            # Cap confidence at 0.6 for inference (since it's less reliable)
            result['language'] = detected_lang
            result['confidence'] = min(confidence * 0.6, 0.6)
            result['details']['inferred_from_extensions'] = True

        return result