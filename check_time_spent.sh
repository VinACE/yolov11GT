#!/bin/bash
# Script to check time spent by visitors

echo "⏰ Visitor Time Tracking Report"
echo "================================"
echo ""

# Get time spent data
curl -s http://localhost:8000/time-spent | python3 -c "
import sys, json
from datetime import datetime

data = json.load(sys.stdin)
visitors = [v for v in data['visitors'] if v['global_id'] != 'TEST_001']

if not visitors:
    print('No visitors detected yet.')
    sys.exit(0)

print('Visitor Details:')
print('=' * 80)
print()

for i, v in enumerate(visitors, 1):
    print(f'Visitor #{i}: {v[\"global_id\"]}')
    print(f'  📅 Entry Time:    {v[\"entry_time\"]}')
    print(f'  🕐 Last Seen:     {v[\"exit_time\"] or \"Still in campus\"}')
    print(f'  ⏱️  Time Spent:    {v[\"time_spent_formatted\"]}')
    print()

# Calculate stats
total_seconds = sum([v['time_spent_seconds'] for v in visitors if v['time_spent_seconds']])
avg_seconds = total_seconds / len(visitors) if visitors else 0

hours = int(avg_seconds // 3600)
minutes = int((avg_seconds % 3600) // 60)
seconds = int(avg_seconds % 60)

if hours > 0:
    avg_formatted = f'{hours}h {minutes}m {seconds}s'
else:
    avg_formatted = f'{minutes}m {seconds}s'

print('📊 Summary Statistics:')
print(f'  Total Visitors:     {len(visitors)}')
print(f'  Average Time Spent: {avg_formatted}')
print()
print('💡 Access full dashboard at: http://localhost:8501')
"
