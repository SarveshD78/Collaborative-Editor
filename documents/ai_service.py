import re
import json
from typing import List, Dict
import requests
from django.conf import settings

class FreeAIWritingAssistant:
    def __init__(self):
        # LanguageTool free API endpoint
        self.languagetool_url = "https://api.languagetool.org/v2/check"
        
    def get_grammar_suggestions(self, text: str) -> List[Dict]:
        """Get grammar and style suggestions using free services"""
        if not text.strip() or len(text) < 5:
            return []
        
        suggestions = []
        
        # Get LanguageTool suggestions (free)
        lt_suggestions = self._get_languagetool_suggestions(text)
        suggestions.extend(lt_suggestions)
        
        # Get rule-based suggestions
        rule_suggestions = self._get_rule_based_suggestions(text)
        suggestions.extend(rule_suggestions)
        
        # Limit to 5 suggestions to keep it manageable
        return suggestions[:5]
    
    def _get_languagetool_suggestions(self, text: str) -> List[Dict]:
        """Get suggestions from free LanguageTool API"""
        try:
            # Limit text length for free API
            text = text[:1000] if len(text) > 1000 else text
            
            response = requests.post(
                self.languagetool_url,
                data={
                    'text': text,
                    'language': 'en-US',
                    'enabledOnly': 'false'
                },
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                suggestions = []
                
                for match in data.get('matches', [])[:3]:  # Limit to 3 suggestions
                    if match.get('replacements'):
                        replacement = match['replacements'][0]['value']
                        original = text[match['offset']:match['offset'] + match['length']]
                        
                        suggestion = {
                            "type": self._categorize_error(match.get('rule', {}).get('category', {}).get('id', '')),
                            "original": original,
                            "suggestion": replacement,
                            "reason": match.get('message', 'Grammar improvement'),
                            "position": match['offset']
                        }
                        suggestions.append(suggestion)
                
                return suggestions
                
        except Exception as e:
            print(f"LanguageTool API Error: {e}")
            return []
        
        return []
    
    def _categorize_error(self, category_id: str) -> str:
        """Categorize LanguageTool errors"""
        if 'GRAMMAR' in category_id:
            return 'grammar'
        elif 'TYPOS' in category_id or 'SPELL' in category_id:
            return 'spelling'
        elif 'STYLE' in category_id:
            return 'style'
        else:
            return 'clarity'
    
    def _get_rule_based_suggestions(self, text: str) -> List[Dict]:
        """Get suggestions using rule-based grammar checking"""
        suggestions = []
        
        # Common grammar rules
        rules = [
            # Capitalization
            {
                'pattern': r'\bi\s',
                'replacement': 'I ',
                'type': 'grammar',
                'reason': "Capitalize the pronoun 'I'"
            },
            # Double spaces
            {
                'pattern': r'\s{2,}',
                'replacement': ' ',
                'type': 'formatting',
                'reason': 'Remove extra spaces'
            },
            # Comma before and/but
            {
                'pattern': r'\s+(and|but|or)\s+',
                'replacement': ', \\1 ',
                'type': 'style',
                'reason': 'Consider adding comma before conjunction'
            },
            # Common typos
            {
                'pattern': r'\brecieve\b',
                'replacement': 'receive',
                'type': 'spelling',
                'reason': "Common spelling error: 'i before e except after c'"
            },
            {
                'pattern': r'\bteh\b',
                'replacement': 'the',
                'type': 'spelling',
                'reason': 'Common typo'
            },
            {
                'pattern': r'\bthier\b',
                'replacement': 'their',
                'type': 'spelling',
                'reason': 'Common spelling error'
            },
            # Punctuation
            {
                'pattern': r'\s+([.!?])',
                'replacement': '\\1',
                'type': 'formatting',
                'reason': 'Remove space before punctuation'
            },
            {
                'pattern': r'([.!?])\s*([a-z])',
                'replacement': '\\1 \\2',
                'type': 'formatting',
                'reason': 'Add space after sentence ending'
            },
        ]
        
        for rule in rules:
            matches = list(re.finditer(rule['pattern'], text, re.IGNORECASE))
            if matches and len(suggestions) < 2:  # Limit rule-based suggestions
                match = matches[0]
                original = match.group()
                replacement = re.sub(rule['pattern'], rule['replacement'], original, flags=re.IGNORECASE)
                
                if original != replacement:  # Only suggest if there's a change
                    suggestion = {
                        "type": rule['type'],
                        "original": original,
                        "suggestion": replacement,
                        "reason": rule['reason'],
                        "position": match.start()
                    }
                    suggestions.append(suggestion)
        
        return suggestions
    
    def get_writing_stats(self, text: str) -> Dict:
        """Get writing statistics"""
        if not text.strip():
            return {
                'words': 0,
                'sentences': 0,
                'readability': 'N/A',
                'avg_sentence_length': 0
            }
        
        words = len(text.split())
        sentences = len([s for s in re.split(r'[.!?]+', text) if s.strip()])
        avg_sentence_length = words / sentences if sentences > 0 else 0
        
        # Simple readability score
        readability = 'Easy' if avg_sentence_length < 15 else 'Medium' if avg_sentence_length < 25 else 'Hard'
        
        return {
            'words': words,
            'sentences': sentences,
            'readability': readability,
            'avg_sentence_length': round(avg_sentence_length, 1)
        }

# Initialize the free service
ai_assistant = FreeAIWritingAssistant()