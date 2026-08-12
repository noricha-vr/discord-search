"""設定のテスト"""

from src.core.config import Settings


class TestExcludeChannelNames:
    """除外チャンネル名設定のテスト"""

    def test_default_value(self):
        """デフォルト値のテスト"""
        settings = Settings(gcp_project_id="test-project")
        assert settings.exclude_channel_names == ["検索用"]

    def test_parse_comma_separated_string(self):
        """カンマ区切り文字列のパースをテスト"""
        settings = Settings(
            gcp_project_id="test-project", exclude_channel_names="検索用,ボット開発,テスト"
        )
        assert settings.exclude_channel_names == ["検索用", "ボット開発", "テスト"]

    def test_parse_string_with_spaces(self):
        """空白を含むカンマ区切り文字列のパースをテスト"""
        settings = Settings(
            gcp_project_id="test-project", exclude_channel_names="検索用 , ボット開発 , テスト"
        )
        assert settings.exclude_channel_names == ["検索用", "ボット開発", "テスト"]

    def test_parse_empty_string(self):
        """空文字列のパースをテスト"""
        settings = Settings(gcp_project_id="test-project", exclude_channel_names="")
        assert settings.exclude_channel_names == []

    def test_parse_whitespace_only(self):
        """空白のみの文字列のパースをテスト"""
        settings = Settings(gcp_project_id="test-project", exclude_channel_names="   ")
        assert settings.exclude_channel_names == []

    def test_parse_list_directly(self):
        """リストを直接渡す場合のテスト"""
        settings = Settings(gcp_project_id="test-project", exclude_channel_names=["検索用", "開発"])
        assert settings.exclude_channel_names == ["検索用", "開発"]

    def test_parse_single_value(self):
        """単一値のテスト"""
        settings = Settings(gcp_project_id="test-project", exclude_channel_names="検索用")
        assert settings.exclude_channel_names == ["検索用"]

    def test_ignore_empty_values_in_comma_list(self):
        """空値を含むカンマ区切りのテスト"""
        settings = Settings(gcp_project_id="test-project", exclude_channel_names="検索用,,テスト,")
        assert settings.exclude_channel_names == ["検索用", "テスト"]
