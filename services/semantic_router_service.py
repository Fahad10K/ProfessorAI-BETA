"""
Semantic Router Service - Intent Classification for Chat Queries
Uses embedding-based routing for ultra-fast, cost-effective intent classification

Benefits:
- 10x faster than LLM-based routing (embedding lookup vs LLM call)
- 100x cheaper (sub-penny vs $0.65 per 10k queries)
- 92-96% accuracy with well-defined routes
- No prompt engineering needed
"""

import logging
from typing import Optional, Dict, Any
from semantic_router import Route
# from semantic_router.layer import RouteLayer
from semantic_router.routers import SemanticRouter
from semantic_router.encoders import OpenAIEncoder
import config

logger = logging.getLogger(__name__)


class SemanticRouterService:
    """
    Fast intent classification using semantic routing.
    Routes queries to: greeting, general_question, or course_query.
    """
    
    def __init__(self):
        """Initialize semantic router with predefined routes."""
        
        # Define routes with example utterances
        self.routes = [
            # Route 1: Greetings and casual conversation
            Route(
                name="greeting",
                utterances=[
                    "hi",
                    "hello",
                    "hey",
                    "good morning",
                    "good afternoon",
                    "good evening",
                    "how are you",
                    "how are you doing",
                    "what's up",
                    "hey there",
                    "greetings",
                    "hi there",
                    "hello there",
                    "namaste",
                    "how do you do",
                    "nice to meet you",
                    "pleased to meet you",
                    "howdy",
                    "yo",
                    "sup"
                ]
            ),
            
            # Route 2: General questions NOT related to educational content
            Route(
                name="general_question",
                utterances=[
                    "what is the weather like today",
                    "tell me a joke",
                    "what's the time",
                    "who is the president",
                    "what is the capital of France",
                    "who won the world cup",
                    "what is the meaning of life",
                    "tell me a story",
                    "what's your name",
                    "where are you from",
                    "how old are you",
                    "do you have feelings",
                    "can you think",
                    "sing me a song",
                    "what's the latest news",
                    "tell me about current events",
                    "what movies are playing",
                    "recommend a restaurant",
                    "what's the score of the game"
                ]
            ),
            
            # Route 3: Course-related queries (requires RAG)
            Route(
                name="course_query",
                utterances=[
                    # Course structure questions
                    "what is covered in module 1",
                    "explain the concept from week 3",
                    "tell me about the course content",
                    "what did we learn in the last lecture",
                    "summarize this week's material",
                    "what are the key topics in this module",
                    "can you explain the assignment",
                    "what is the quiz about",
                    "help me understand this topic from the course",
                    "what does the lecture say about",
                    "according to the course material",
                    "based on what we learned",
                    "from the course notes",
                    "in the lecture slides",
                    "the professor mentioned",
                    "explain this concept from class",
                    "what did the course cover about",
                    "review the material on",
                    "go over the lesson about",
                    "what are the learning objectives",
                    
                    # Educational subject matter questions (from our 18 courses)
                    "explain artificial intelligence",
                    "what is machine learning",
                    "how does deep learning work",
                    "tell me about neural networks",
                    "what is robotics",
                    "explain computer vision",
                    "what are convolutional neural networks",
                    "how do transformers work in AI",
                    "explain cyber security concepts",
                    "what is encryption",
                    "tell me about network security",
                    "explain python programming",
                    "what are data structures",
                    "how does object oriented programming work",
                    "explain generative AI",
                    "what is natural language processing",
                    "tell me about reinforcement learning",
                    "explain virtual reality technology",
                    "what is augmented reality",
                    "how does VR hardware work",
                    "explain business management principles",
                    "what is accounting",
                    "tell me about financial statements",
                    "explain psychology concepts",
                    "what is cognitive psychology",
                    "tell me about behavioral theories",
                    "explain political science",
                    "what is sociology",
                    "explain language learning techniques",
                    "what is phonetics",
                    "how do I learn hindi",
                    "teach me arabic grammar",
                    "explain sanskrit pronunciation"
                ]
            )
        ]
        
        # Initialize encoder (uses OpenAI embeddings)
        try:
            self.encoder = OpenAIEncoder(
                openai_api_key=config.OPENAI_API_KEY,
                name="text-embedding-3-small"  # Faster and cheaper than 3-large
            )
            
            # Create semantic router
            self.router = SemanticRouter(
                encoder=self.encoder,
                routes=self.routes,
                auto_sync="local"
            )
            
            logger.info("✅ Semantic Router initialized with 3 routes (greeting, general_question, course_query)")
            self.enabled = True
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize Semantic Router: {e}")
            logger.warning("⚠️ Falling back to rule-based routing")
            self.enabled = False
    
    def is_query_course_specific(self, query: str) -> bool:
        """
        Fast validation to check if a query is actually about course content.
        Used to determine if course_id filter should be applied.
        
        Args:
            query: User's question or message
            
        Returns:
            True if query is about learning/course content, False for general queries
        
        Examples:
            "What is robotics?" → True (educational content)
            "Explain neural networks" → True (educational content)
            "What is the weather today?" → False (general query)
            "Tell me a joke" → False (general query)
        """
        query_lower = query.lower().strip()
        
        # Course/learning indicators
        course_indicators = [
            # Educational terms
            "learn", "study", "understand", "explain", "teach", "lesson", "module",
            "course", "lecture", "tutorial", "chapter", "topic", "concept", "theory",
            "assignment", "homework", "quiz", "exam", "test", "material", "content",
            "week", "semester", "class", "professor", "instructor",
            
            # Subject-specific terms (from our 18 courses)
            "ai", "machine learning", "robotics", "cyber security", "python",
            "generative", "neural network", "algorithm", "programming", "code",
            "english speaking", "hindi", "arabic", "sanskrit", "translation",
            "psychology", "sociology", "political science", "accountancy", "business",
            "chemistry", "virtual reality", "vr", "accounting", "finance",
            
            # Question words about learning
            "what is", "what are", "how does", "how do", "why does", "why is",
            "can you explain", "tell me about", "describe", "define", "summarize"
        ]
        
        # Non-course indicators (general chat)
        non_course_indicators = [
            "weather", "time", "date", "joke", "story", "news", "current events",
            "sports score", "movie", "restaurant", "recipe", "directions",
            "how are you", "what's up", "tell me a joke", "sing a song"
        ]
        
        # Check for non-course indicators first (higher priority)
        for indicator in non_course_indicators:
            if indicator in query_lower:
                logger.info(f"⚠️ Query is NOT course-specific (matched: '{indicator}')")
                return False
        
        # Check for course indicators
        for indicator in course_indicators:
            if indicator in query_lower:
                logger.info(f"✅ Query IS course-specific (matched: '{indicator}')")
                return True
        
        # Default: if it's a question or educational in nature, consider it course-related
        question_words = ["what", "how", "why", "when", "where", "who", "explain", "define", "describe"]
        if any(query_lower.startswith(qw) for qw in question_words):
            # It's a question, likely educational
            logger.info("✅ Query IS course-specific (question format)")
            return True
        
        # Default to False for safety (don't restrict if unclear)
        logger.info("⚠️ Query specificity unclear, defaulting to general (no filter)")
        return False
    
    def classify_intent(self, query: str) -> Dict[str, Any]:
        """
        Classify the intent of a user query.
        
        Args:
            query: User's question or message
            
        Returns:
            Dict with:
                - route_name: "greeting", "general_question", or "course_query"
                - confidence: Similarity score (0-1)
                - should_use_rag: Boolean flag
        """
        
        if not self.enabled:
            # Fallback to simple rule-based routing
            return self._rule_based_classify(query)
        
        try:
            # Route using semantic similarity
            route_choice = self.router(query)
            
            if route_choice and route_choice.name:
                route_name = route_choice.name
                
                # Check if we got a valid route
                if route_name in ["greeting", "general_question", "course_query"]:
                    should_use_rag = (route_name == "course_query")
                    
                    logger.info(f"🎯 Routed query to: {route_name} (RAG: {should_use_rag})")
                    
                    return {
                        "route_name": route_name,
                        "confidence": getattr(route_choice, 'similarity_score', 0.8) or 0.8,
                        "should_use_rag": should_use_rag
                    }
            
            # If no clear route, default to course_query (safe fallback)
            logger.info("⚠️ No clear route found, defaulting to course_query")
            return {
                "route_name": "course_query",
                "confidence": 0.5,
                "should_use_rag": True
            }
            
        except Exception as e:
            logger.error(f"❌ Semantic routing error: {e}, falling back to rule-based")
            return self._rule_based_classify(query)
    
    def _rule_based_classify(self, query: str) -> Dict[str, Any]:
        """
        Simple rule-based fallback classification.
        Used when semantic router fails or is disabled.
        """
        query_lower = query.lower().strip()
        
        # Check for greetings
        greeting_keywords = ["hi", "hello", "hey", "good morning", "good afternoon", 
                            "good evening", "namaste", "howdy", "what's up", "how are you"]
        
        if any(query_lower.startswith(keyword) for keyword in greeting_keywords):
            if len(query_lower.split()) <= 5:  # Short greeting
                return {
                    "route_name": "greeting",
                    "confidence": 0.9,
                    "should_use_rag": False
                }
        
        # Check for course-related keywords
        course_keywords = ["module", "lecture", "course", "assignment", "quiz", 
                          "topic", "lesson", "material", "content", "week", 
                          "professor", "class", "learning", "study"]
        
        if any(keyword in query_lower for keyword in course_keywords):
            return {
                "route_name": "course_query",
                "confidence": 0.7,
                "should_use_rag": True
            }
        
        # Default to general question
        return {
            "route_name": "general_question",
            "confidence": 0.6,
            "should_use_rag": False
        }
    
    def get_greeting_response(self, query: str, language: str = "English") -> str:
        """
        Generate a friendly greeting response without LLM call.
        Ultra-fast (< 1ms) and free.
        """
        import random
        
        # Multilingual greetings
        greetings = {
            "English": [
                "Hello! I'm ProfessorAI, your learning assistant. How can I help you with your studies today?",
                "Hi there! Ready to learn something new? Ask me anything about your courses!",
                "Hey! I'm here to help you learn. What would you like to know?",
                "Greetings! I'm your AI teacher. What can I help you understand today?",
            ],
            "Hindi": [
                "नमस्ते! मैं ProfessorAI हूं, आपका सीखने का सहायक। आज मैं आपकी पढ़ाई में कैसे मदद कर सकता हूं?",
                "हैलो! कुछ नया सीखने के लिए तैयार हैं? मुझसे अपने कोर्स के बारे में कुछ भी पूछें!",
            ],
            "Bengali": [
                "হ্যালো! আমি ProfessorAI, আপনার শেখার সহায়ক। আজ আপনার পড়াশোনায় আমি কীভাবে সাহায্য করতে পারি?",
            ],
            "Tamil": [
                "வணக்கம்! நான் ProfessorAI, உங்கள் கற்றல் உதவியாளர். இன்று உங்கள் படிப்பில் நான் எப்படி உதவ முடியும்?",
            ],
            "Telugu": [
                "నమస్కారం! నేను ProfessorAI, మీ అభ్యాస సహాయకుడిని. ఈ రోజు మీ చదువులో నేను ఎలా సహాయం చేయగలను?",
            ]
        }
        
        # Get language-specific greetings or default to English
        language_greetings = greetings.get(language, greetings["English"])
        
        return random.choice(language_greetings)
