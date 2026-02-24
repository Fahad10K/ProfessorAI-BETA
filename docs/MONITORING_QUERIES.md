# Teaching Orchestrator Monitoring Queries

## Redis Queries

### Active Sessions Count
```bash
redis-cli KEYS "teaching:session:*:context" | wc -l
```

### List All Active Sessions
```bash
redis-cli KEYS "teaching:session:*:context"
```

### Get Specific Session State
```bash
redis-cli GET "teaching:session:{session_id}:context"
```

### Get Session Metrics
```bash
redis-cli GET "teaching:session:{session_id}:metrics"
```

### Get Session History
```bash
redis-cli GET "teaching:session:{session_id}:history"
```

### Check Memory Usage
```bash
redis-cli INFO memory | grep used_memory_human
```

### Monitor Operations Per Second
```bash
redis-cli INFO stats | grep instantaneous_ops_per_sec
```

## PostgreSQL Analytics Queries

### Total Teaching Sessions Today
```sql
SELECT COUNT(DISTINCT session_id) 
FROM messages 
WHERE created_at >= CURRENT_DATE 
  AND message_type = 'voice';
```

### Questions Asked Per Course
```sql
SELECT 
    course_id,
    COUNT(*) as question_count,
    COUNT(DISTINCT user_id) as unique_students
FROM messages 
WHERE role = 'user' 
  AND message_type = 'voice'
  AND course_id IS NOT NULL
GROUP BY course_id
ORDER BY question_count DESC;
```

### Average Questions Per Session
```sql
SELECT 
    session_id,
    COUNT(*) as questions,
    MIN(created_at) as session_start,
    MAX(created_at) as session_end,
    EXTRACT(EPOCH FROM (MAX(created_at) - MIN(created_at)))/60 as duration_minutes
FROM messages 
WHERE role = 'user' 
  AND message_type = 'voice'
GROUP BY session_id
HAVING COUNT(*) > 0
ORDER BY questions DESC
LIMIT 20;
```

### Most Active Students
```sql
SELECT 
    user_id,
    COUNT(DISTINCT session_id) as sessions,
    COUNT(*) as questions,
    MAX(created_at) as last_activity
FROM messages 
WHERE role = 'user' 
  AND message_type = 'voice'
GROUP BY user_id
ORDER BY questions DESC
LIMIT 50;
```

### Popular Topics (Most Questions)
```sql
SELECT 
    course_id,
    COUNT(*) as question_count,
    AVG(EXTRACT(EPOCH FROM (
        SELECT MIN(m2.created_at) 
        FROM messages m2 
        WHERE m2.session_id = m1.session_id 
          AND m2.role = 'assistant' 
          AND m2.created_at > m1.created_at
    ) - m1.created_at)) as avg_response_time_sec
FROM messages m1
WHERE role = 'user' 
  AND message_type = 'voice'
  AND course_id IS NOT NULL
GROUP BY course_id
ORDER BY question_count DESC;
```

## Python Monitoring Scripts

### Get Active Session Count
```python
import redis
r = redis.from_url("redis://localhost:6379")

active_sessions = len(r.keys("teaching:session:*:context"))
print(f"Active sessions: {active_sessions}")
```

### Get All Session Metrics
```python
import redis
import json

r = redis.from_url("redis://localhost:6379")

metrics_keys = r.keys("teaching:session:*:metrics")
total_questions = 0
total_interruptions = 0

for key in metrics_keys:
    data = json.loads(r.get(key))
    total_questions += data.get('questions_asked', 0)
    total_interruptions += data.get('interruptions', 0)

print(f"Total questions across all active sessions: {total_questions}")
print(f"Total interruptions: {total_interruptions}")
print(f"Interruption rate: {total_interruptions/total_questions*100:.1f}%")
```

### Monitor Session State Distribution
```python
import redis
import json
from collections import Counter

r = redis.from_url("redis://localhost:6379")

context_keys = r.keys("teaching:session:*:context")
states = []

for key in context_keys:
    data = json.loads(r.get(key))
    states.append(data.get('current_state'))

state_counts = Counter(states)
print("Session states:")
for state, count in state_counts.most_common():
    print(f"  {state}: {count}")
```

### Real-time Dashboard Data
```python
import redis
import json
from datetime import datetime

def get_dashboard_metrics():
    r = redis.from_url("redis://localhost:6379")
    
    # Active sessions
    active_sessions = len(r.keys("teaching:session:*:context"))
    
    # Aggregate metrics
    metrics_keys = r.keys("teaching:session:*:metrics")
    total_questions = 0
    total_segments = 0
    
    for key in metrics_keys:
        data = json.loads(r.get(key))
        total_questions += data.get('questions_asked', 0)
        current_seg = data.get('current_segment', 0)
        total_segs = data.get('total_segments', 1)
        total_segments += (current_seg / total_segs * 100)
    
    avg_progress = total_segments / active_sessions if active_sessions > 0 else 0
    avg_questions = total_questions / active_sessions if active_sessions > 0 else 0
    
    return {
        "active_sessions": active_sessions,
        "total_questions": total_questions,
        "avg_questions_per_session": round(avg_questions, 2),
        "avg_progress_percent": round(avg_progress, 1),
        "timestamp": datetime.now().isoformat()
    }

# Usage
print(json.dumps(get_dashboard_metrics(), indent=2))
```

## CloudWatch/Datadog Integration

### Custom Metrics to Track
```python
import boto3

cloudwatch = boto3.client('cloudwatch')

def push_teaching_metrics():
    r = redis.from_url(config.REDIS_URL)
    
    metrics = [
        {
            'MetricName': 'ActiveTeachingSessions',
            'Value': len(r.keys("teaching:session:*:context")),
            'Unit': 'Count'
        },
        {
            'MetricName': 'TotalQuestions',
            'Value': sum_questions_from_redis(r),
            'Unit': 'Count'
        },
        {
            'MetricName': 'AvgSessionProgress',
            'Value': calculate_avg_progress(r),
            'Unit': 'Percent'
        }
    ]
    
    cloudwatch.put_metric_data(
        Namespace='ProfAI/Teaching',
        MetricData=metrics
    )
```

## Performance Benchmarks

### Expected Performance Metrics

| Metric | Target | Alert Threshold |
|--------|--------|-----------------|
| Active Sessions | 0-10,000 | > 8,000 (scale up) |
| Redis Memory | < 2GB | > 1.8GB |
| Avg Response Time | < 100ms | > 200ms |
| Questions/Session | 3-8 | < 1 (engagement issue) |
| Interruption Rate | 10-30% | > 50% (UX issue) |

### Load Testing
```bash
# Simulate 1000 concurrent sessions
for i in {1..1000}; do
  redis-cli SET "teaching:session:load_test_$i:context" '{"session_id":"load_test_'$i'"}' EX 1800 &
done
wait

# Check memory impact
redis-cli INFO memory | grep used_memory_human
```

## Alerting Rules

### Critical Alerts
- Redis connection failures
- Active sessions > 8000 (scale up needed)
- Redis memory > 80% (increase capacity)
- Error rate > 5%

### Warning Alerts
- Active sessions > 5000 (prepare to scale)
- Redis memory > 60%
- Avg response time > 200ms
- Interruption rate > 50%

## Cleanup & Maintenance

### Manual Cleanup (if needed)
```bash
# Delete expired sessions (TTL handles this automatically)
redis-cli KEYS "teaching:session:*:context" | xargs -L1 redis-cli DEL

# Check for orphaned keys
redis-cli SCAN 0 MATCH "teaching:*" COUNT 1000
```

### Database Archival
```sql
-- Archive old sessions (older than 90 days)
INSERT INTO messages_archive 
SELECT * FROM messages 
WHERE created_at < NOW() - INTERVAL '90 days'
  AND message_type = 'voice';

DELETE FROM messages 
WHERE created_at < NOW() - INTERVAL '90 days'
  AND message_type = 'voice';
```
