TravelMate Itinerary Fix v3

Purpose:
- Prevent RAG itinerary highlights from mentioning another destination that exists
  in the TravelMate destinations table.
- Apply the same guard to initial plan generation and itinerary regeneration.
- If all retrieved highlights are filtered, the existing _day_wise_itinerary
  fallback produces a generic destination-specific suggestion rather than
  inserting unrelated city text.

Apply:
1. Back up travelmate_backend/app/services/plan_orchestrator.py.
2. Copy the file from this patch to the same path in your project.
3. From travelmate_backend, run:
   python -m pytest tests/test_itinerary_destination_grounding.py -q

Notes:
- No database writes or migrations are performed.
- No ML model, feature dataset, RAG service, or LLM gateway is replaced.
- This guard catches known destination names in the database. It cannot guarantee
  every factual statement is correct, so verify the generated itinerary manually.
