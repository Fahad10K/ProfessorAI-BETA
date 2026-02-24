"""
Recommendation Service - Self-Improvement Agent
Analyzes student progress, quiz performance, and learning patterns
to recommend quizzes, topics to revisit, and next courses.
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class RecommendationService:
    """Generates personalized learning recommendations from student data."""

    def __init__(self):
        try:
            from services.database_service_v2 import get_database_service
            self.db = get_database_service()
            logger.info("RecommendationService initialized")
        except Exception as e:
            logger.error(f"RecommendationService init failed: {e}")
            self.db = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_recommendations(self, user_id: int) -> Dict[str, Any]:
        """
        Master endpoint: returns a complete recommendation payload.
        {
            "weak_modules":    [...],   # modules where quiz score < 60%
            "recommended_quizzes": [...],  # quizzes the student should take/retake
            "next_topics":     [...],   # incomplete topics to study next
            "next_courses":    [...],   # courses the student hasn't started
            "summary":         "..."    # natural-language summary
        }
        """
        if not self.db:
            return {"error": "Database service not available"}

        try:
            enrolled = self._get_enrolled_courses(user_id)
            all_courses = self.db.get_all_courses()
            quiz_history = self.db.get_user_quiz_responses(user_id)
            quiz_stats = self.db.get_user_quiz_stats(user_id)

            weak_modules = self._find_weak_modules(user_id, enrolled, quiz_history)
            rec_quizzes = self._recommend_quizzes(user_id, enrolled, quiz_history)
            next_topics = self._find_next_topics(user_id, enrolled)
            next_courses = self._suggest_next_courses(user_id, enrolled, all_courses)
            summary = self._build_summary(
                quiz_stats, weak_modules, rec_quizzes, next_topics, next_courses
            )

            return {
                "user_id": user_id,
                "quiz_stats": quiz_stats,
                "weak_modules": weak_modules,
                "recommended_quizzes": rec_quizzes,
                "next_topics": next_topics,
                "next_courses": next_courses,
                "summary": summary,
            }
        except Exception as e:
            logger.error(f"Error generating recommendations for user {user_id}: {e}")
            return {"error": str(e)}

    # ------------------------------------------------------------------
    # Enrolled courses helper
    # ------------------------------------------------------------------

    def _get_enrolled_courses(self, user_id: int) -> List[Dict]:
        """Get courses the student has any progress in."""
        query = """
            SELECT DISTINCT up.course_id,
                   c.title as course_title,
                   c.course_number
            FROM user_progress up
            JOIN courses c ON up.course_id = c.id
            WHERE up.user_id = %s
        """
        try:
            rows = self.db.execute_query(query, (user_id,), fetch='all')
            return [dict(r) for r in rows] if rows else []
        except Exception:
            return []

    # ------------------------------------------------------------------
    # Weak-module detection
    # ------------------------------------------------------------------

    def _find_weak_modules(
        self, user_id: int, enrolled: List[Dict], quiz_history: List[Dict]
    ) -> List[Dict]:
        """
        Identify modules where the student scored below 60 % on the most
        recent quiz attempt.
        """
        weak = []
        # Build a map: quiz_id -> latest attempt
        latest_by_quiz: Dict[str, Dict] = {}
        for qr in quiz_history:
            qid = qr.get('quiz_id', '')
            if qid not in latest_by_quiz:
                latest_by_quiz[qid] = qr  # already sorted DESC by submitted_at

        for qid, attempt in latest_by_quiz.items():
            total = attempt.get('total_questions', 1) or 1
            score = attempt.get('score', 0) or 0
            pct = (score / total) * 100
            if pct < 60:
                # Try to resolve module info from quiz
                quiz_info = self._get_quiz_info(qid)
                weak.append({
                    "quiz_id": qid,
                    "score_percent": round(pct, 1),
                    "score": score,
                    "total_questions": total,
                    "quiz_title": quiz_info.get('title', qid),
                    "course_id": quiz_info.get('course_id'),
                    "module_title": quiz_info.get('module_title'),
                })
        return weak

    def _get_quiz_info(self, quiz_id: str) -> Dict:
        """Fetch quiz metadata including module title."""
        query = """
            SELECT q.title, q.course_id, q.module_id, m.title as module_title
            FROM quizzes q
            LEFT JOIN modules m ON q.module_id = m.id
            WHERE q.quiz_id = %s
        """
        try:
            row = self.db.execute_query(query, (quiz_id,), fetch='one')
            return dict(row) if row else {}
        except Exception:
            return {}

    # ------------------------------------------------------------------
    # Quiz recommendations
    # ------------------------------------------------------------------

    def _recommend_quizzes(
        self, user_id: int, enrolled: List[Dict], quiz_history: List[Dict]
    ) -> List[Dict]:
        """
        Recommend quizzes the student should take or retake:
        1. Module quizzes they haven't attempted yet
        2. Quizzes they failed (< 60 %) — suggest retake
        """
        recommendations = []

        # Quizzes already attempted
        attempted_ids = {qr.get('quiz_id') for qr in quiz_history}

        # Find all quizzes for enrolled courses
        for course in enrolled:
            cid = course.get('course_id')
            if not cid:
                continue
            query = """
                SELECT q.quiz_id, q.title, q.quiz_type, q.course_id,
                       m.title as module_title, m.week
                FROM quizzes q
                LEFT JOIN modules m ON q.module_id = m.id
                WHERE q.course_id = %s
                ORDER BY m.week ASC NULLS LAST
            """
            try:
                rows = self.db.execute_query(query, (cid,), fetch='all')
                if not rows:
                    continue
                for row in rows:
                    r = dict(row)
                    qid = r.get('quiz_id')
                    if qid not in attempted_ids:
                        recommendations.append({
                            "quiz_id": qid,
                            "title": r.get('title'),
                            "reason": "not_attempted",
                            "message": f"You haven't taken this quiz yet",
                            "course_title": course.get('course_title'),
                            "module_title": r.get('module_title'),
                        })
            except Exception:
                continue

        # Add retake suggestions for failed quizzes
        latest_by_quiz: Dict[str, Dict] = {}
        for qr in quiz_history:
            qid = qr.get('quiz_id', '')
            if qid not in latest_by_quiz:
                latest_by_quiz[qid] = qr

        for qid, attempt in latest_by_quiz.items():
            total = attempt.get('total_questions', 1) or 1
            score = attempt.get('score', 0) or 0
            pct = (score / total) * 100
            if pct < 60:
                quiz_info = self._get_quiz_info(qid)
                recommendations.append({
                    "quiz_id": qid,
                    "title": quiz_info.get('title', qid),
                    "reason": "failed",
                    "message": f"Score {round(pct)}% — retake recommended",
                    "last_score_percent": round(pct, 1),
                    "module_title": quiz_info.get('module_title'),
                })

        return recommendations

    # ------------------------------------------------------------------
    # Next topics to study
    # ------------------------------------------------------------------

    def _find_next_topics(self, user_id: int, enrolled: List[Dict]) -> List[Dict]:
        """Find incomplete topics the student should study next."""
        next_topics = []

        for course in enrolled:
            cid = course.get('course_id')
            if not cid:
                continue

            # Get all topics in course
            query = """
                SELECT t.id as topic_id, t.title as topic_title,
                       m.id as module_id, m.title as module_title, m.week,
                       t.order_index
                FROM topics t
                JOIN modules m ON t.module_id = m.id
                WHERE m.course_id = %s
                ORDER BY m.week, t.order_index
            """
            try:
                all_topics = self.db.execute_query(query, (cid,), fetch='all')
                if not all_topics:
                    continue

                # Get completed topic IDs
                completed_query = """
                    SELECT topic_id FROM user_progress
                    WHERE user_id = %s AND course_id = %s
                    AND status = 'completed' AND topic_id IS NOT NULL
                """
                completed_rows = self.db.execute_query(
                    completed_query, (user_id, cid), fetch='all'
                )
                completed_ids = {r['topic_id'] for r in completed_rows} if completed_rows else set()

                # Find first few incomplete topics
                count = 0
                for t in all_topics:
                    td = dict(t)
                    if td['topic_id'] not in completed_ids:
                        next_topics.append({
                            "course_id": cid,
                            "course_title": course.get('course_title'),
                            "module_title": td.get('module_title'),
                            "module_week": td.get('week'),
                            "topic_id": td['topic_id'],
                            "topic_title": td.get('topic_title'),
                        })
                        count += 1
                        if count >= 3:  # max 3 per course
                            break
            except Exception:
                continue

        return next_topics

    # ------------------------------------------------------------------
    # Next courses
    # ------------------------------------------------------------------

    def _suggest_next_courses(
        self, user_id: int, enrolled: List[Dict], all_courses: List[Dict]
    ) -> List[Dict]:
        """Suggest courses the student hasn't started yet."""
        enrolled_ids = {c.get('course_id') for c in enrolled}
        suggestions = []
        for course in all_courses:
            cid = course.get('id')
            if cid not in enrolled_ids:
                suggestions.append({
                    "course_id": cid,
                    "course_number": course.get('course_number'),
                    "title": course.get('title'),
                    "description": course.get('description', ''),
                    "level": course.get('level', 'Beginner'),
                    "country": course.get('country'),
                })
        return suggestions

    # ------------------------------------------------------------------
    # Natural-language summary
    # ------------------------------------------------------------------

    def _build_summary(
        self,
        quiz_stats: Dict,
        weak_modules: List,
        rec_quizzes: List,
        next_topics: List,
        next_courses: List,
    ) -> str:
        total = quiz_stats.get('total_attempts', 0)
        avg = quiz_stats.get('avg_score', 0) or 0
        passed = quiz_stats.get('passed_count', 0) or 0

        parts = []

        if total == 0:
            parts.append(
                "You haven't taken any quizzes yet. Start with your first module quiz!"
            )
        else:
            parts.append(
                f"You've attempted {total} quiz(es) with an average score of "
                f"{avg:.0f}% and passed {passed}."
            )

        if weak_modules:
            titles = [w.get('module_title') or w.get('quiz_title', '') for w in weak_modules[:3]]
            parts.append(
                f"Focus on improving: {', '.join(titles)}."
            )

        not_attempted = [q for q in rec_quizzes if q.get('reason') == 'not_attempted']
        if not_attempted:
            parts.append(
                f"You have {len(not_attempted)} quiz(es) you haven't tried yet."
            )

        if next_topics:
            parts.append(
                f"Next up: continue studying '{next_topics[0].get('topic_title', '')}'."
            )

        if next_courses:
            parts.append(
                f"There are {len(next_courses)} more course(s) available for you to explore."
            )

        return " ".join(parts)
