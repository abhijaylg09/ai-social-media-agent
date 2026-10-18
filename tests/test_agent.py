import unittest
import json
from app.tools import search_trending_topics, analyze_engagement_score, publish_to_social_api
from app.storage import init_db, save_post, get_post_by_thread_id
from app.graph import social_agent_graph
from langgraph.types import Command

class TestSocialMediaAgent(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        init_db()

    def test_trending_topics_tool(self):
        result = search_trending_topics.invoke({"niche": "technology"})
        self.assertIn("trends", result)
        self.assertGreaterEqual(len(result["trends"]), 1)
        self.assertTrue(any("AIAgents" in h or "AI" in h for h in result["trends"][0]["hashtags"]))

    def test_engagement_score_tool(self):
        sample_tweet = "⚡ Autonomous AI agents are reshaping how software is built. Are you using them? 👇 #AI #LangGraph"
        score_data = analyze_engagement_score.invoke({"post_content": sample_tweet, "platform": "twitter"})
        self.assertIn("predicted_virality_score", score_data)
        self.assertGreaterEqual(score_data["predicted_virality_score"], 60)
        self.assertEqual(score_data["platform"], "twitter")

    def test_social_api_publish_tool(self):
        res = publish_to_social_api.invoke({"platform": "twitter", "post_content": "Hello World", "is_dry_run": False})
        self.assertTrue(res["success"])
        self.assertEqual(res["http_status"], 201)
        self.assertIn("https://x.com/", res["post_url"])

    def test_langgraph_hitl_workflow(self):
        thread_id = "test-thread-hitl-001"
        post_id = "test-post-001"
        initial_state = {
            "id": post_id,
            "thread_id": thread_id,
            "topic": "Microservices to Modular Monoliths",
            "tone": "insightful",
            "platforms": ["twitter", "linkedin"],
            "drafts": {},
            "review_feedback": {},
            "approval_status": "pending",
            "human_feedback": "",
            "scheduled_time": "",
            "published_status": "pending",
            "published_results": {},
            "history_trace": [],
            "current_step": "start"
        }

        # Step 1: Run graph until human approval interrupt
        config = {"configurable": {"thread_id": thread_id}}
        state_after_interrupt = social_agent_graph.invoke(initial_state, config=config)
        self.assertIn("twitter", state_after_interrupt["drafts"])
        self.assertIn("linkedin", state_after_interrupt["drafts"])
        self.assertEqual(state_after_interrupt["approval_status"], "pending")

        # Step 2: Resume with human approval
        resume_payload = {
            "action": "approved",
            "feedback": "Approved for dispatch",
            "drafts": state_after_interrupt["drafts"]
        }
        resumed_state = social_agent_graph.invoke(Command(resume=resume_payload), config=config)
        self.assertEqual(resumed_state["published_status"], "published")
        self.assertIn("twitter", resumed_state["published_results"])

if __name__ == "__main__":
    unittest.main()
