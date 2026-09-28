class FakeTelegramSender:
    def __init__(self):
        self.events = []
        self._topic_ids = {}

    def fake_call(self, method, data, silent=False):
        self.events.append({"event": "api", "method": method, "data": dict(data)})
        return {"ok": True, "result": {"message_id": len(self.events)}}

    def fake_get_or_create_topic(
        self, chat_id, acc_name, tag_emoji, state, is_admin=False,
        force_recreate=False, delivery_kind="normal", topic_group="account",
    ):
        key = (chat_id, acc_name, delivery_kind, topic_group)
        suffix = "" if topic_group == "account" else f"__target_{topic_group}"
        suffix += "_trials" if delivery_kind == "trial" else ""
        topic = f"TOPIC::{chat_id}::{acc_name}{suffix}"
        self._topic_ids[key] = topic
        state[f"{chat_id}_{acc_name}{suffix}"] = {"id": topic, "name": acc_name}
        self.events.append(
            {
                "event": "topic",
                "chat_id": chat_id,
                "username": acc_name,
                "topic_id": topic,
                "tag": tag_emoji,
                "delivery_kind": delivery_kind,
                "topic_group": topic_group,
            }
        )
        return topic

    def fake_send_video(
        self, chat_id, t_id, caption, video_path, topics_state, username,
        tag, source_hash=None, topic_group="account", delivery_kind="normal",
        story_link_url=None, **_kwargs,
    ):
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
                "topic_group": topic_group,
                "delivery_kind": delivery_kind,
                "story_link_url": story_link_url,
            }
        )
        return True, t_id
