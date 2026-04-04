from convert_to_mp4.presets import Preset, PresetConfig, get_preset_config


class TestPresetEnum:
    def test_all_presets_exist(self):
        assert Preset.TV.value == "tv"
        assert Preset.MOBILE.value == "mobile"
        assert Preset.ARCHIVE.value == "archive"
        assert Preset.QUICK.value == "quick"

    def test_preset_from_string(self):
        assert Preset("tv") is Preset.TV
        assert Preset("mobile") is Preset.MOBILE


class TestGetPresetConfig:
    def test_tv_preset(self):
        config = get_preset_config(Preset.TV)
        assert config.min_quality == 192
        assert config.max_quality == 256
        assert config.description == "High quality for smart TVs"

    def test_mobile_preset(self):
        config = get_preset_config(Preset.MOBILE)
        assert config.min_quality == 128
        assert config.max_quality == 160

    def test_archive_preset(self):
        config = get_preset_config(Preset.ARCHIVE)
        assert config.min_quality == 256
        assert config.max_quality == 320

    def test_quick_preset(self):
        config = get_preset_config(Preset.QUICK)
        assert config.min_quality == 128
        assert config.max_quality == 192

    def test_all_presets_have_config(self):
        for preset in Preset:
            config = get_preset_config(preset)
            assert isinstance(config, PresetConfig)
            assert config.min_quality <= config.max_quality
