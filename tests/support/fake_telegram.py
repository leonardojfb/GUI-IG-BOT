class FakeTelegramSender:
    def __init__(self):
        self.events = []
        self._topic_ids = {}

    def fake_call(self, method, data, silent=False):
        self.events.append({"event": "api", "method": method, "data": dict(data)})
        return {"ok": True, "result": {"message_id": len(self.events)}}

    def fake_get_or_create_topic(self, chat_id, acc_name, tag_emoji, state, is_admin=False, force_recreate=False):
        key = (chat_id, acc_name)
        topic = f"TOPIC::{chat_id}::{acc_name}"
        self._topic_ids[key] = topic
        state[f"{chat_id}_{acc_name}"] = {"id": topic, "name": acc_name}
        self.events.append(
            {
                "event": "topic",
                "chat_id": chat_id,
                "username": acc_name,
                "topic_id": topic,
                "tag": tag_emoji,
            }
        )
        return topic

    def fake_send_video(self, chat_id, t_id, caption, video_path, topics_state, username, tag, source_hash=None):
        self.events.append(
            {
                "event": "video",
                "chat_id": chat_id,
                "topic_id": t_id,
                "caption": caption,
                "video_path": video_path,
                "username": username,
                "tag": tag,
                "source_hash": source_hash,
            }
        )
        return True, t_id
