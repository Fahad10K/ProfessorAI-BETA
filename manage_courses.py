#!/usr/bin/env python3
"""
Course Management Utility - Validate, repair, and manage the course database
"""

import os
import json
import logging
from typing import List, Dict, Any

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def load_config():
    """Load configuration."""
    import sys
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    import config
    return config

def validate_course_structure(course: Dict[str, Any], course_index: int = 0) -> List[str]:
    """Validate a single course structure and return list of issues."""
    issues = []
    
    # Check required fields
    required_fields = ['course_id', 'course_title', 'modules']
    for field in required_fields:
        if field not in course:
            issues.append(f"Course {course_index}: Missing required field '{field}'")
    
    # Validate course_id
    if 'course_id' in course:
        if not isinstance(course['course_id'], int) or course['course_id'] <= 0:
            issues.append(f"Course {course_index}: Invalid course_id '{course.get('course_id')}'")
    
    # Validate course_title
    if 'course_title' in course:
        if not isinstance(course['course_title'], str) or not course['course_title'].strip():
            issues.append(f"Course {course_index}: Invalid course_title")
    
    # Validate modules
    if 'modules' in course:
        if not isinstance(course['modules'], list):
            issues.append(f"Course {course_index}: Modules must be a list")
        else:
            for i, module in enumerate(course['modules']):
                if not isinstance(module, dict):
                    issues.append(f"Course {course_index}, Module {i}: Must be a dictionary")
                    continue
                
                # Check module fields
                if 'week' not in module:
                    issues.append(f"Course {course_index}, Module {i}: Missing 'week' field")
                elif not isinstance(module['week'], int) or module['week'] <= 0:
                    issues.append(f"Course {course_index}, Module {i}: Invalid week number")
                
                if 'title' not in module:
                    issues.append(f"Course {course_index}, Module {i}: Missing 'title' field")
                elif not isinstance(module['title'], str) or not module['title'].strip():
                    issues.append(f"Course {course_index}, Module {i}: Invalid title")
                
                if 'sub_topics' not in module:
                    issues.append(f"Course {course_index}, Module {i}: Missing 'sub_topics' field")
                elif not isinstance(module['sub_topics'], list):
                    issues.append(f"Course {course_index}, Module {i}: sub_topics must be a list")
                else:
                    # Validate sub_topics
                    for j, sub_topic in enumerate(module['sub_topics']):
                        if not isinstance(sub_topic, dict):
                            issues.append(f"Course {course_index}, Module {i}, Sub-topic {j}: Must be a dictionary")
                            continue
                        
                        if 'title' not in sub_topic:
                            issues.append(f"Course {course_index}, Module {i}, Sub-topic {j}: Missing 'title' field")
                        elif not isinstance(sub_topic['title'], str):
                            issues.append(f"Course {course_index}, Module {i}, Sub-topic {j}: Invalid title")
                        
                        if 'content' not in sub_topic:
                            issues.append(f"Course {course_index}, Module {i}, Sub-topic {j}: Missing 'content' field")
                        elif not isinstance(sub_topic['content'], str):
                            issues.append(f"Course {course_index}, Module {i}, Sub-topic {j}: Invalid content")
    
    return issues

def validate_courses_database(file_path: str) -> Dict[str, Any]:
    """Validate the entire courses database."""
    result = {
        'valid': True,
        'issues': [],
        'stats': {},
        'courses': []
    }
    
    if not os.path.exists(file_path):
        result['valid'] = False
        result['issues'].append(f"Course database file not found: {file_path}")
        return result
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        result['valid'] = False
        result['issues'].append(f"Failed to load JSON: {e}")
        return result
    
    # Check if data is in correct format (should be a list)
    if not isinstance(data, list):
        result['valid'] = False
        result['issues'].append("Course database must be a list of courses")
        return result
    
    # Validate each course
    course_ids = []
    course_titles = []
    
    for i, course in enumerate(data):
        course_issues = validate_course_structure(course, i)
        result['issues'].extend(course_issues)
        
        if course_issues:
            result['valid'] = False
        
        # Check for duplicate IDs and titles
        if 'course_id' in course:
            if course['course_id'] in course_ids:
                result['issues'].append(f"Duplicate course_id: {course['course_id']}")
                result['valid'] = False
            else:
                course_ids.append(course['course_id'])
        
        if 'course_title' in course:
            if course['course_title'] in course_titles:
                result['issues'].append(f"Duplicate course_title: {course['course_title']}")
                result['valid'] = False
            else:
                course_titles.append(course['course_title'])
    
    # Generate statistics
    result['stats'] = {
        'total_courses': len(data),
        'course_ids': sorted(course_ids),
        'total_modules': sum(len(course.get('modules', [])) for course in data),
        'total_sub_topics': sum(
            len(sub_topic) 
            for course in data 
            for module in course.get('modules', []) 
            for sub_topic in [module.get('sub_topics', [])]
        )
    }
    
    result['courses'] = data
    return result

def repair_courses_database(file_path: str, backup: bool = True) -> bool:
    """Attempt to repair common issues in the courses database."""
    logging.info("Starting course database repair...")
    
    if backup and os.path.exists(file_path):
        backup_path = f"{file_path}.backup"
        import shutil
        shutil.copy2(file_path, backup_path)
        logging.info(f"Created backup: {backup_path}")
    
    validation_result = validate_courses_database(file_path)
    
    if validation_result['valid']:
        logging.info("Database is already valid, no repairs needed")
        return True
    
    courses = validation_result['courses']
    repaired = False
    
    # Fix missing or invalid course IDs
    used_ids = set()
    next_id = 1
    
    for course in courses:
        if 'course_id' not in course or not isinstance(course['course_id'], int) or course['course_id'] <= 0:
            while next_id in used_ids:
                next_id += 1
            course['course_id'] = next_id
            logging.info(f"Assigned course_id {next_id} to course '{course.get('course_title', 'Unknown')}'")
            repaired = True
        
        used_ids.add(course['course_id'])
        next_id = max(next_id, course['course_id'] + 1)
    
    # Fix missing or invalid titles
    for i, course in enumerate(courses):
        if 'course_title' not in course or not isinstance(course['course_title'], str) or not course['course_title'].strip():
            course['course_title'] = f"Course {course.get('course_id', i+1)}"
            logging.info(f"Assigned default title to course {course['course_id']}")
            repaired = True
    
    # Fix modules structure
    for course in courses:
        if 'modules' not in course or not isinstance(course['modules'], list):
            course['modules'] = []
            logging.info(f"Fixed modules structure for course '{course['course_title']}'")
            repaired = True
        
        for i, module in enumerate(course['modules']):
            if not isinstance(module, dict):
                continue
            
            if 'week' not in module or not isinstance(module['week'], int):
                module['week'] = i + 1
                repaired = True
            
            if 'title' not in module or not isinstance(module['title'], str):
                module['title'] = f"Module {module['week']}"
                repaired = True
            
            if 'sub_topics' not in module or not isinstance(module['sub_topics'], list):
                module['sub_topics'] = []
                repaired = True
            
            for j, sub_topic in enumerate(module['sub_topics']):
                if not isinstance(sub_topic, dict):
                    continue
                
                if 'title' not in sub_topic or not isinstance(sub_topic['title'], str):
                    sub_topic['title'] = f"Topic {j + 1}"
                    repaired = True
                
                if 'content' not in sub_topic or not isinstance(sub_topic['content'], str):
                    sub_topic['content'] = ""
                    repaired = True
    
    if repaired:
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(courses, f, indent=4, ensure_ascii=False)
            logging.info("Database repaired and saved successfully")
            return True
        except Exception as e:
            logging.error(f"Failed to save repaired database: {e}")
            return False
    else:
        logging.info("No repairs were needed")
        return True

def main():
    """Main function to run course management operations."""
    config = load_config()
    
    print("=== Course Database Management ===")
    print(f"Database file: {config.OUTPUT_JSON_PATH}")
    
    # Validate database
    print("\n1. Validating course database...")
    validation_result = validate_courses_database(config.OUTPUT_JSON_PATH)
    
    if validation_result['valid']:
        print("✅ Database is valid!")
    else:
        print("❌ Database has issues:")
        for issue in validation_result['issues']:
            print(f"  - {issue}")
    
    # Show statistics
    if validation_result['stats']:
        print(f"\n📊 Database Statistics:")
        print(f"  - Total courses: {validation_result['stats']['total_courses']}")
        print(f"  - Total modules: {validation_result['stats']['total_modules']}")
        print(f"  - Total sub-topics: {validation_result['stats']['total_sub_topics']}")
        print(f"  - Course IDs: {validation_result['stats']['course_ids']}")
    
    # Offer to repair if needed
    if not validation_result['valid']:
        response = input("\n🔧 Would you like to attempt automatic repair? (y/n): ")
        if response.lower() == 'y':
            success = repair_courses_database(config.OUTPUT_JSON_PATH)
            if success:
                print("✅ Database repaired successfully!")
                # Re-validate
                validation_result = validate_courses_database(config.OUTPUT_JSON_PATH)
                if validation_result['valid']:
                    print("✅ Database is now valid!")
                else:
                    print("⚠️ Some issues remain:")
                    for issue in validation_result['issues']:
                        print(f"  - {issue}")
            else:
                print("❌ Repair failed!")

if __name__ == "__main__":
    main()
