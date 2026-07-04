from convert_to_mp4.audio import (
    AudioInfo,
    LoudnessStats,
    build_loudnorm_filter,
    calculate_optimal_bitrate,
    should_reencode,
)


class TestCalculateOptimalBitrate:
    def test_ac3_applies_two_thirds_ratio(self):
        assert calculate_optimal_bitrate(384, "ac3", 128, 320) == 256

    def test_eac3_applies_two_thirds_ratio(self):
        assert calculate_optimal_bitrate(640, "eac3", 128, 320) == 320

    def test_mp3_applies_seven_tenths_ratio(self):
        assert calculate_optimal_bitrate(320, "mp3", 128, 320) == 224

    def test_aac_keeps_same_bitrate(self):
        assert calculate_optimal_bitrate(192, "aac", 128, 256) == 192

    def test_unknown_codec_applies_three_quarters(self):
        assert calculate_optimal_bitrate(256, "flac", 128, 256) == 192

    def test_clamps_to_min_quality(self):
        assert calculate_optimal_bitrate(64, "mp3", 128, 256) == 128

    def test_clamps_to_max_quality(self):
        assert calculate_optimal_bitrate(512, "ac3", 128, 256) == 256

    def test_rounds_up_to_nearest_standard(self):
        assert calculate_optimal_bitrate(200, "aac", 128, 320) == 224

    def test_zero_bitrate_returns_192(self):
        assert calculate_optimal_bitrate(0, "ac3", 128, 256) == 192

    def test_none_bitrate_returns_192(self):
        assert calculate_optimal_bitrate(None, "ac3", 128, 256) == 192

    def test_bitrate_in_bps_converted_to_kbps(self):
        assert calculate_optimal_bitrate(192000, "aac", 128, 256) == 192

    def test_high_kbps_not_mistaken_for_bps(self):
        assert calculate_optimal_bitrate(1001, "aac", 128, 320) == 320


class TestShouldReencode:
    def test_aac_stereo_no_force_returns_false(self):
        info = AudioInfo(codec="aac", channels=2, bitrate=192)
        assert should_reencode(info, force_audio=False) is False

    def test_non_aac_returns_true(self):
        info = AudioInfo(codec="ac3", channels=2, bitrate=384)
        assert should_reencode(info, force_audio=False) is True

    def test_more_than_two_channels_returns_true(self):
        info = AudioInfo(codec="aac", channels=6, bitrate=384)
        assert should_reencode(info, force_audio=False) is True

    def test_force_audio_returns_true(self):
        info = AudioInfo(codec="aac", channels=2, bitrate=192)
        assert should_reencode(info, force_audio=True) is True

    def test_mono_aac_no_force_returns_false(self):
        info = AudioInfo(codec="aac", channels=1, bitrate=128)
        assert should_reencode(info, force_audio=False) is False


class TestBuildLoudnormFilter:
    def test_measurement_filter_downmixes_and_prints_json(self):
        filter_str = build_loudnorm_filter()

        assert filter_str.startswith("aformat=channel_layouts=stereo,loudnorm=")
        assert "I=-16" in filter_str
        assert "TP=-1.5" in filter_str
        assert "LRA=11" in filter_str
        assert filter_str.endswith(":print_format=json")

    def test_apply_filter_includes_measured_values(self):
        stats = LoudnessStats(
            input_i=-27.2,
            input_tp=-4.9,
            input_lra=16.1,
            input_thresh=-38.1,
            target_offset=0.4,
        )

        filter_str = build_loudnorm_filter(stats)

        assert filter_str.startswith("aformat=channel_layouts=stereo,loudnorm=")
        assert "measured_I=-27.2" in filter_str
        assert "measured_TP=-4.9" in filter_str
        assert "measured_LRA=16.1" in filter_str
        assert "measured_thresh=-38.1" in filter_str
        assert "offset=0.4" in filter_str
        assert "linear=true" in filter_str
        assert "print_format" not in filter_str
