"""
Session Initialization Service

Handles the intelligent session-start flow:
  1. Greet user by name
  2. Show progress summary (last session, completed courses/topics)
  3. Offer choices: resume, switch course, ask questions
  4. Generate pre-lesson quiz from previous session

This service is stateless — it queries the database and produces
text/data for the WebSocket server to stream via TTS.
"""

import logging
import json
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)


class SessionInitService:
    """Generates greeting, progress summary, and pre-lesson content."""

    def __init__(self, database_service):
        """
        Args:
            database_service: DatabaseServiceV2 instance (already initialized)
        """
        self.db = database_service

    def build_welcome(self, user_id: int, user_name: str = "") -> Dict[str, Any]:
        """
        Build the full welcome payload for a user starting/resuming a session.

        Returns dict with:
          - greeting_text: TTS-friendly greeting string
          - summary: structured progress data for the frontend
          - has_previous_session: bool
          - suggested_action: 'resume' | 'choose_course' | 'first_time'
          - resume_info: {course_id, module_index, topic_index, ...} if resumable
        """
        from services.realtime_orchestrator import _clean_first_name
        first_name = _clean_first_name(user_name)

        # Fetch learning summary from DB
        learning = self.db.get_user_learning_summary(user_id)
        last_session = self.db.get_last_session_context(user_id)

        # Determine if this is a first-time user or returning
        courses_started = learning.get('courses_started', 0)
        is_first_time = courses_started == 0

        if is_first_time:
            return self._build_first_time_welcome(first_name, user_id)

        return self._build_returning_welcome(first_name, user_id, learning, last_session)

    def _build_first_time_welcome(self, name: str, user_id: int) -> Dict[str, Any]:
        """Welcome for a brand-new user with no progress."""
        courses = self.db.get_all_courses_summary()
        course_count = len(courses)

        greeting = (
            f"Welcome {name}! I'm your AI professor. "
            f"We have {course_count} courses available for you. "
            f"Would you like me to show you the available courses, "
            f"or would you like to start with the first one?"
        )

        return {
            'greeting_text': greeting,
            'summary': {
                'is_first_time': True,
                'available_courses': course_count,
                'courses': [
                    {'id': c['id'], 'title': c['title'], 'level': c.get('level'),
                     'modules': c.get('module_count', 0), 'topics': c.get('topic_count', 0)}
                    for c in courses[:10]  # Cap at 10 for TTS
                ],
            },
            'has_previous_session': False,
            'suggested_action': 'choose_course',
            'resume_info': None,
        }

    def _build_returning_welcome(
        self, name: str, user_id: int, learning: Dict, last_session: Optional[Dict]
    ) -> Dict[str, Any]:
        """Welcome for a returning user with existing progress."""

        courses_started = learning.get('courses_started', 0)
        courses_completed = learning.get('courses_completed', 0)
        total_completed = learning.get('total_topics_completed', 0)
        last_course_title = learning.get('last_course_title', 'your course')
        last_module_title = learning.get('last_module_title')
        last_topic_title = learning.get('last_topic_title')
        last_course_id = learning.get('last_course_id')

        # Build progress sentence
        progress_parts = []
        if courses_completed > 0:
            progress_parts.append(
                f"You've completed {courses_completed} course{'s' if courses_completed > 1 else ''}"
            )
        if total_completed > 0:
            progress_parts.append(f"{total_completed} topics overall")

        progress_sentence = " and ".join(progress_parts) if progress_parts else ""

        # Build last-session sentence
        last_session_sentence = ""
        if last_course_title:
            last_session_sentence = f"Last time, we were working on {last_course_title}"
            if last_module_title:
                last_session_sentence += f", in the module on {last_module_title}"
            if last_topic_title:
                last_session_sentence += f", covering {last_topic_title}"
            last_session_sentence += "."

        # Build course progress details for the most recent course
        course_detail_sentence = ""
        course_details = learning.get('course_details', [])
        if course_details:
            latest = course_details[0]
            pct = latest.get('completion_pct', 0)
            completed = latest.get('completed_topics', 0)
            total = latest.get('total_topics', 0)
            remaining = total - completed
            if remaining > 0:
                course_detail_sentence = (
                    f"You've completed {completed} out of {total} topics "
                    f"in {latest['title']}, that's {pct:.0f}% done. "
                    f"{remaining} topic{'s' if remaining > 1 else ''} remaining."
                )
            else:
                course_detail_sentence = f"You've completed all topics in {latest['title']}!"

        # Compose greeting
        greeting_parts = [f"Welcome back {name}!"]
        if progress_sentence:
            greeting_parts.append(progress_sentence + ".")
        if last_session_sentence:
            greeting_parts.append(last_session_sentence)
        if course_detail_sentence:
            greeting_parts.append(course_detail_sentence)

        greeting_parts.append(
            "Would you like to continue where we left off, "
            "switch to a different course, or do you have any questions first?"
        )

        greeting_text = " ".join(greeting_parts)

        # Build resume info
        resume_info = None
        if last_course_id:
            # Find the next incomplete topic in the last course
            resume_info = self._find_resume_point(user_id, last_course_id)

        return {
            'greeting_text': greeting_text,
            'summary': {
                'is_first_time': False,
                'courses_started': courses_started,
                'courses_completed': courses_completed,
                'total_topics_completed': total_completed,
                'last_course_id': last_course_id,
                'last_course_title': last_course_title,
                'last_module_title': last_module_title,
                'last_topic_title': last_topic_title,
                'course_details': course_details,
            },
            'has_previous_session': True,
            'suggested_action': 'resume' if resume_info else 'choose_course',
            'resume_info': resume_info,
        }

    def _find_resume_point(self, user_id: int, course_id: int) -> Optional[Dict]:
        """
        Find the next topic to teach in a course — the first incomplete topic
        after the last completed one.
        """
        try:
            course_data = self.db.get_course_with_content(course_id)
            if not course_data:
                return None

            modules = course_data.get('modules', [])
            if not modules:
                return None

            # Get completed topic IDs for this course
            progress = self.db.get_user_progress(user_id, course_id)
            completed_topic_ids = set()
            for p in progress:
                if p.get('status') == 'completed' and p.get('topic_id'):
                    completed_topic_ids.add(p['topic_id'])

            # Walk through modules/topics in order to find first incomplete
            for m_idx, module in enumerate(modules):
                topics = module.get('topics', module.get('sub_topics', []))
                for t_idx, topic in enumerate(topics):
                    topic_id = topic.get('id')
                    if topic_id not in completed_topic_ids:
                        return {
                            'course_id': course_id,
                            'course_title': course_data.get('title', ''),
                            'module_index': m_idx,
                            'module_title': module.get('title', ''),
                            'sub_topic_index': t_idx,
                            'topic_title': topic.get('title', ''),
                            'topic_id': topic_id,
                            'module_id': module.get('id'),
                            '_course_data': course_data,  # cached to avoid duplicate DB call
                        }

            # All topics completed
            return None
        except Exception as e:
            logger.error(f"Error finding resume point: {e}")
            return None

    def build_course_list_text(self, user_id: int = None) -> str:
        """Build a TTS-friendly listing of available courses."""
        courses = self.db.get_all_courses_summary()
        if not courses:
            return "There are no courses available at the moment."

        lines = [f"We have {len(courses)} courses available:"]
        for i, c in enumerate(courses[:10], 1):
            modules = c.get('module_count', 0)
            topics = c.get('topic_count', 0)
            lines.append(
                f"Course {i}: {c['title']}. "
                f"It has {modules} modules and {topics} topics."
            )

        lines.append("Which course would you like to start? Just say the course number.")
        return " ".join(lines)

    def build_module_list_text(self, course_id: int) -> str:
        """Build a TTS-friendly listing of modules in a course."""
        modules = self.db.get_course_modules_summary(course_id)
        if not modules:
            return "This course doesn't have any modules yet."

        lines = [f"This course has {len(modules)} modules:"]
        for i, m in enumerate(modules, 1):
            topics = m.get('topic_count', 0)
            lines.append(
                f"Module {i}: {m['title']}. It covers {topics} topics."
            )

        lines.append("Which module would you like to start with?")
        return " ".join(lines)

    def build_topic_list_text(self, course_id: int, module_index: int) -> str:
        """Build a TTS-friendly listing of topics in a module."""
        try:
            course_data = self.db.get_course_with_content(course_id)
            if not course_data:
                return "Course not found."

            modules = course_data.get('modules', [])
            if module_index >= len(modules):
                return f"Module {module_index + 1} not found."

            module = modules[module_index]
            topics = module.get('topics', module.get('sub_topics', []))
            if not topics:
                return "This module doesn't have any topics."

            lines = [f"Module {module_index + 1}: {module['title']} has {len(topics)} topics:"]
            for i, t in enumerate(topics, 1):
                lines.append(f"Topic {i}: {t.get('title', 'Unknown')}.")

            lines.append("Which topic would you like to start with?")
            return " ".join(lines)
        except Exception as e:
            logger.error(f"Error building topic list: {e}")
            return "I couldn't load the topics for this module."

    def build_progress_text(self, user_id: int, user_name: str = "") -> str:
        """Build a TTS-friendly progress report."""
        from services.realtime_orchestrator import _clean_first_name
        name = _clean_first_name(user_name)

        learning = self.db.get_user_learning_summary(user_id)
        courses_started = learning.get('courses_started', 0)
        courses_completed = learning.get('courses_completed', 0)
        total_completed = learning.get('total_topics_completed', 0)

        if courses_started == 0:
            return f"{name}, you haven't started any courses yet. Would you like to see what's available?"

        lines = [f"Here's your progress report, {name}."]
        lines.append(
            f"You've started {courses_started} course{'s' if courses_started > 1 else ''} "
            f"and completed {total_completed} topics overall."
        )

        for detail in learning.get('course_details', [])[:5]:
            pct = detail.get('completion_pct', 0)
            lines.append(
                f"{detail['title']}: {detail['completed_topics']} of "
                f"{detail['total_topics']} topics done, {pct:.0f}% complete."
            )

        if courses_completed > 0:
            lines.append(f"You've fully completed {courses_completed} course{'s' if courses_completed > 1 else ''}. Great job!")

        lines.append("What would you like to do next?")
        return " ".join(lines)
