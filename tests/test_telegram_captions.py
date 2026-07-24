import organizadortg


def test_load_clean_captions_keeps_multiline_paragraphs_together(tmp_path):
    captions_file = tmp_path / "captions.txt"
    captions_file.write_text(
        "Primera línea\nSegunda línea\n#uno #dos\n\n"
        "Otra caption\n#tres\n",
        encoding="utf-8",
    )

    assert organizadortg.load_clean_captions(str(captions_file)) == [
        "Primera línea\nSegunda línea\n#uno #dos",
        "Otra caption\n#tres",
    ]


def test_load_clean_captions_keeps_blank_lines_inside_caption(tmp_path):
    captions_file = tmp_path / "captions.txt"
    captions_file.write_text(
        "New York Architecture\n\n"
        "Some cities don't have skylines.\n\n"
        "They have signatures.\n\n"
        "#NewYork #Architecture\n",
        encoding="utf-8",
    )

    assert organizadortg.load_clean_captions(str(captions_file)) == [
        "New York Architecture\n\n"
        "Some cities don't have skylines.\n\n"
        "They have signatures.\n\n"
        "#NewYork #Architecture",
    ]


def test_caption_for_video_keeps_caption_order_per_video():
    pool = ["caption uno", "caption dos"]

    assert organizadortg.caption_for_video(pool, 0) == "caption uno"
    assert organizadortg.caption_for_video(pool, 1) == "caption dos"
    assert organizadortg.caption_for_video(pool, 2) == "caption uno"
