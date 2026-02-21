"""
Course Generator - Handles curriculum and content generation
"""

from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser, StrOutputParser
from langchain_core.runnables import RunnableParallel, RunnablePassthrough
from langchain_core.documents import Document
from typing import List
import logging
import config
from models.schemas import CourseLMS

class CourseGenerator:
    """Generates complete courses with curriculum and content."""
    
    def __init__(self):
        self.curriculum_model = ChatOpenAI(
            model=config.CURRICULUM_GENERATION_MODEL, 
            temperature=0.2, 
            openai_api_key=config.OPENAI_API_KEY
        )
        self.content_model = ChatOpenAI(
            model=config.CONTENT_GENERATION_MODEL, 
            temperature=0.5, 
            openai_api_key=config.OPENAI_API_KEY
        )
        self.curriculum_parser = JsonOutputParser(pydantic_object=CourseLMS)
        self.content_parser = StrOutputParser()
    
    def generate_course(self, documents: List[Document], retriever, course_title: str = None, source_filter: str = None) -> CourseLMS:
        """Generate a complete course with curriculum and content."""
        try:
            # Filter documents by source if specified
            if source_filter:
                logging.info(f"Filtering documents by source: {source_filter}")
                filtered_documents = [doc for doc in documents if doc.metadata.get('source') == source_filter]
                logging.info(f"Filtered from {len(documents)} to {len(filtered_documents)} documents")
                documents = filtered_documents
                
                if not documents:
                    raise Exception(f"No documents found for source: {source_filter}")
            
            # Step 1: Generate curriculum structure
            logging.info("Generating curriculum structure...")
            curriculum = self._generate_curriculum(documents, course_title)
            
            if not curriculum:
                raise Exception("Curriculum generation failed")
            
            # Step 2: Generate content for each topic with filtered retriever
            logging.info("Generating detailed content...")
            filtered_retriever = self._create_filtered_retriever(retriever, source_filter)
            final_course = self._generate_content(curriculum, filtered_retriever)
            
            return final_course
            
        except Exception as e:
            logging.error(f"Course generation failed: {e}")
            raise e
    
    def _generate_curriculum(self, documents: List[Document], course_title: str = None) -> CourseLMS:
        """Generate the curriculum structure."""
        if not documents:
            logging.error("Cannot generate curriculum: No documents provided")
            return None
        
        # Limit context to stay within GPT-5's 272K token limit (roughly 68K tokens = ~272,000 characters)
        max_context_chars = 200000
        context_parts = []
        current_length = 0
        
        for doc in documents:
            doc_content = doc.page_content
            if current_length + len(doc_content) > max_context_chars:
                # If adding this document would exceed the limit, truncate it
                remaining_chars = max_context_chars - current_length
                if remaining_chars > 100:  # Only add if we have meaningful space left
                    context_parts.append(doc_content[:remaining_chars] + "...")
                break
            context_parts.append(doc_content)
            current_length += len(doc_content) + 5  # +5 for separator
        
        context_str = "\n---\n".join(context_parts)
        logging.info(f"Context length: {len(context_str)} characters (limited to {max_context_chars})")
        
        template = """
        You are an expert instructional designer tasked with creating a university-level course curriculum.
        Analyze the provided context from various documents and generate a logical, week-by-week learning path.

        CONTEXT:
        {context}

        INSTRUCTIONS:
        1. Create a comprehensive course structure with a clear title.
        2. Organize the content into weekly modules.
        3. For each week, define a clear module title and a list of specific sub-topics to be covered.
        4. Ensure the learning path is logical and progressive.
        5. The course should span a reasonable number of weeks based on the provided content.
        
        {format_instructions}
        """
        
        prompt = ChatPromptTemplate.from_template(
            template,
            partial_variables={"format_instructions": self.curriculum_parser.get_format_instructions()}
        )
        
        try:
            chain = prompt | self.curriculum_model | self.curriculum_parser
            result = chain.invoke({"context": context_str})
            
            logging.info(f"Raw curriculum result type: {type(result)}")
            logging.info(f"Raw curriculum result: {result}")
            
            # Handle case where result might be a dict instead of CourseLMS object
            if isinstance(result, dict):
                logging.info("Converting dict result to CourseLMS object")
                curriculum = CourseLMS(**result)
            else:
                curriculum = result
            
            # Validate that curriculum has modules
            if not hasattr(curriculum, 'modules') or not curriculum.modules:
                logging.error("Generated curriculum has no modules")
                return None
            
            # Override title if provided
            if course_title and hasattr(curriculum, 'course_title'):
                curriculum.course_title = course_title
            
            logging.info(f"Generated curriculum with {len(curriculum.modules)} modules")
            return curriculum
            
        except Exception as e:
            logging.error(f"Error generating curriculum: {e}")
            import traceback
            logging.error(f"Traceback: {traceback.format_exc()}")
            return None
    
    def _generate_content(self, curriculum: CourseLMS, retriever) -> CourseLMS:
        """Generate detailed content for each topic in the curriculum."""
        if not retriever:
            raise ValueError("Retriever must be provided for content generation")
        
        template = """
        You are an expert university professor. Write detailed, clear, and engaging lecture content
        for the given topic based *only* on the provided context.

        CONTEXT:
        {context}

        TOPIC:
        {topic}

        INSTRUCTIONS:
        - Explain the topic thoroughly using the provided context.
        - Use examples from the context if available.
        - Structure the content with clear headings and paragraphs.
        - The tone should be academic and authoritative, yet accessible.
        - Provide comprehensive coverage of the topic.
        """
        
        prompt = ChatPromptTemplate.from_template(template)
        
        # Build RAG chain for content generation
        def get_context(topic_dict):
            topic = topic_dict['topic']
            docs = retriever.get_relevant_documents(topic)
            return {"context": "\n---\n".join(doc.page_content for doc in docs), "topic": topic}
        
        content_chain = (
            RunnablePassthrough()
            | get_context
            | prompt
            | self.content_model
            | self.content_parser
        )
        
        # Generate content for each sub-topic
        for module in curriculum.modules:
            logging.info(f"Generating content for Week {module.week}: {module.title}")
            
            for sub_topic in module.sub_topics:
                try:
                    logging.info(f"  Generating content for: {sub_topic.title}")
                    
                    content = content_chain.invoke({"topic": sub_topic.title})
                    sub_topic.content = content
                    
                    logging.info(f"  Content generated successfully for: {sub_topic.title}")
                    
                except Exception as e:
                    logging.error(f"  Failed to generate content for {sub_topic.title}: {e}")
                    sub_topic.content = f"Content generation failed for this topic. Error: {str(e)}"
        
        logging.info("Content generation completed for all topics")
        return curriculum
    
    def _create_filtered_retriever(self, retriever, source_filter: str = None):
        """Create a filtered retriever that only returns documents from specified source."""
        if not source_filter:
            return retriever
        
        # Get the underlying vectorstore from the retriever
        vectorstore = retriever.vectorstore
        
        # Create a new retriever with source filter
        try:
            filtered_retriever = vectorstore.as_retriever(
                search_type="similarity",
                search_kwargs={
                    "k": 50,
                    "filter": {"source": source_filter}
                }
            )
            logging.info(f"Created filtered retriever for source: {source_filter}")
            return filtered_retriever
        except Exception as e:
            logging.warning(f"Could not create filtered retriever: {e}. Using original retriever.")
            return retriever