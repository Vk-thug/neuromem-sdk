"""
Auto-tagging system for NeuroMem.

Automatically generates tags for memories based on:
- Topics and themes
- Named entities
- Intent classification
- Sentiment analysis
"""

import json
from typing import List, Dict, Any
import openai


class AutoTagger:
    """
    Automatic tag generation for memory items.
    
    Generates hierarchical tags like:
    - topic:machine_learning
    - preference:technical_depth
    - entity:person:john
    - intent:learning
    - sentiment:positive
    """
    
    def __init__(self, llm_model: str = "gpt-4o-mini"):
        """
        Initialize auto-tagger.
        
        Args:
            llm_model: LLM model for tag generation
        """
        self.llm_model = llm_model
    
    def generate_tags(self, content: str, max_tags: int = 10) -> List[str]:
        """
        Generate tags for memory content.
        
        Args:
            content: Memory content text
            max_tags: Maximum number of tags to generate
        
        Returns:
            List of hierarchical tags
        """
        prompt = f"""Analyze the following text and generate relevant tags.

Text:
{content}

Generate tags in these categories:
- topic: (e.g., topic:machine_learning, topic:cooking)
- preference: (e.g., preference:technical_depth, preference:concise_answers)
- entity: (e.g., entity:person:john, entity:place:paris, entity:concept:neural_networks)
- intent: (e.g., intent:learning, intent:question, intent:feedback)
- sentiment: (e.g., sentiment:positive, sentiment:neutral, sentiment:negative)

Return a JSON array of up to {max_tags} tags:
["tag1", "tag2", ...]

Use lowercase and underscores. Return ONLY the JSON array."""

        try:
            response = openai.chat.completions.create(
                model=self.llm_model,
                messages=[
                    {"role": "system", "content": "You are a tag generation system that creates hierarchical tags for text."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3
            )
            
            tags_json = response.choices[0].message.content.strip()
            if tags_json.startswith("```"):
                tags_json = tags_json.split("```")[1]
                if tags_json.startswith("json"):
                    tags_json = tags_json[4:]
            
            tags = json.loads(tags_json)
            return tags[:max_tags]
        
        except Exception as e:
            print(f"Error generating tags: {e}")
            return self._fallback_tags(content)
    
    def _fallback_tags(self, content: str) -> List[str]:
        """
        Fallback tag generation using simple heuristics.
        
        Args:
            content: Memory content
        
        Returns:
            List of basic tags
        """
        tags = []
        content_lower = content.lower()
        
        # Topic keywords
        topic_keywords = {
            "machine learning": "topic:machine_learning",
            "ai": "topic:artificial_intelligence",
            "python": "topic:programming",
            "data": "topic:data_science",
            "web": "topic:web_development",
            "database": "topic:databases",
        }
        
        for keyword, tag in topic_keywords.items():
            if keyword in content_lower:
                tags.append(tag)
        
        # Preference indicators
        if any(word in content_lower for word in ["prefer", "like", "want"]):
            tags.append("intent:preference")
        
        # Question indicators
        if any(word in content_lower for word in ["what", "how", "why", "when", "where"]):
            tags.append("intent:question")
        
        # Sentiment (very basic)
        positive_words = ["good", "great", "excellent", "love", "like"]
        negative_words = ["bad", "poor", "hate", "dislike", "terrible"]
        
        if any(word in content_lower for word in positive_words):
            tags.append("sentiment:positive")
        elif any(word in content_lower for word in negative_words):
            tags.append("sentiment:negative")
        else:
            tags.append("sentiment:neutral")
        
        return tags
    
    def extract_entities(self, content: str) -> List[Dict[str, str]]:
        """
        Extract named entities from content.
        
        Args:
            content: Text content
        
        Returns:
            List of entities with type and value
        """
        prompt = f"""Extract named entities from the following text.

Text:
{content}

Return JSON array of entities:
[
  {{"type": "person|place|organization|concept|technology", "value": "entity_name"}}
]

Return ONLY the JSON array."""

        try:
            response = openai.chat.completions.create(
                model=self.llm_model,
                messages=[
                    {"role": "system", "content": "You are an entity extraction system."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3
            )
            
            entities_json = response.choices[0].message.content.strip()
            if entities_json.startswith("```"):
                entities_json = entities_json.split("```")[1]
                if entities_json.startswith("json"):
                    entities_json = entities_json[4:]
            
            entities = json.loads(entities_json)
            return entities
        
        except Exception as e:
            print(f"Error extracting entities: {e}")
            return []
    
    def classify_intent(self, content: str) -> str:
        """
        Classify the intent of the content.
        
        Args:
            content: Text content
        
        Returns:
            Intent classification
        """
        content_lower = content.lower()
        
        # Simple rule-based classification
        if any(word in content_lower for word in ["what", "how", "why", "explain"]):
            return "question"
        elif any(word in content_lower for word in ["prefer", "like", "want"]):
            return "preference"
        elif any(word in content_lower for word in ["thank", "thanks", "appreciate"]):
            return "gratitude"
        elif any(word in content_lower for word in ["help", "assist", "support"]):
            return "request"
        else:
            return "statement"
    
    def analyze_sentiment(self, content: str) -> Dict[str, Any]:
        """
        Analyze sentiment of content.
        
        Args:
            content: Text content
        
        Returns:
            Sentiment analysis results
        """
        # Simple sentiment analysis
        content_lower = content.lower()
        
        positive_words = ["good", "great", "excellent", "love", "like", "happy", "wonderful"]
        negative_words = ["bad", "poor", "hate", "dislike", "terrible", "awful", "sad"]
        
        pos_count = sum(1 for word in positive_words if word in content_lower)
        neg_count = sum(1 for word in negative_words if word in content_lower)
        
        if pos_count > neg_count:
            sentiment = "positive"
            score = min(1.0, pos_count / 5.0)
        elif neg_count > pos_count:
            sentiment = "negative"
            score = min(1.0, neg_count / 5.0)
        else:
            sentiment = "neutral"
            score = 0.5
        
        return {
            "sentiment": sentiment,
            "score": score,
            "positive_count": pos_count,
            "negative_count": neg_count
        }
    
    def enrich_memory(self, content: str) -> Dict[str, Any]:
        """
        Full enrichment of memory content with tags and metadata.
        
        Args:
            content: Memory content
        
        Returns:
            Enrichment data
        """
        return {
            "tags": self.generate_tags(content),
            "entities": self.extract_entities(content),
            "intent": self.classify_intent(content),
            "sentiment": self.analyze_sentiment(content)
        }
