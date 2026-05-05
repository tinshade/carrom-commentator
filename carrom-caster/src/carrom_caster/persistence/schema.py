from __future__ import annotations

import sqlalchemy as sa

metadata = sa.MetaData()

player_groups = sa.Table(
    "player_groups",
    metadata,
    sa.Column("id", sa.Text, primary_key=True),
    sa.Column("name", sa.Text, nullable=False),
    sa.Column("last_used", sa.Text, nullable=False),
)

player_group_members = sa.Table(
    "player_group_members",
    metadata,
    sa.Column("group_id", sa.Text, sa.ForeignKey("player_groups.id"), nullable=False),
    sa.Column("position", sa.Integer, nullable=False),
    sa.Column("player_id", sa.Text, nullable=False),
    sa.Column("player_name", sa.Text, nullable=False),
    sa.PrimaryKeyConstraint("group_id", "position"),
)

matches = sa.Table(
    "matches",
    metadata,
    sa.Column("id", sa.Text, primary_key=True),
    sa.Column("mode", sa.Text, nullable=False),
    sa.Column("board_number", sa.Integer, nullable=False),
    sa.Column("boards_won_0", sa.Integer, nullable=False),
    sa.Column("boards_won_1", sa.Integer, nullable=False),
    sa.Column("queen_state", sa.Text, nullable=False),
    sa.Column("queen_pocketed_by_index", sa.Integer, nullable=True),
    sa.Column("white_coins_on_board", sa.Integer, nullable=False),
    sa.Column("black_coins_on_board", sa.Integer, nullable=False),
    sa.Column("current_turn_index", sa.Integer, nullable=False),
    sa.Column("is_active", sa.Integer, nullable=False),
    sa.Column("created_at", sa.Text, nullable=False),
)

match_players = sa.Table(
    "match_players",
    metadata,
    sa.Column("match_id", sa.Text, sa.ForeignKey("matches.id"), nullable=False),
    sa.Column("position", sa.Integer, nullable=False),
    sa.Column("player_id", sa.Text, nullable=False),
    sa.Column("player_name", sa.Text, nullable=False),
    sa.Column("team_index", sa.Integer, nullable=True),
    sa.PrimaryKeyConstraint("match_id", "position"),
)

match_teams = sa.Table(
    "match_teams",
    metadata,
    sa.Column("match_id", sa.Text, sa.ForeignKey("matches.id"), nullable=False),
    sa.Column("team_index", sa.Integer, nullable=False),
    sa.Column("team_id", sa.Text, nullable=False),
    sa.Column("team_name", sa.Text, nullable=False),
    sa.PrimaryKeyConstraint("match_id", "team_index"),
)

match_scores = sa.Table(
    "match_scores",
    metadata,
    sa.Column("match_id", sa.Text, sa.ForeignKey("matches.id"), nullable=False),
    sa.Column("player_id", sa.Text, nullable=False),
    sa.Column("points", sa.Integer, nullable=False),
    sa.PrimaryKeyConstraint("match_id", "player_id"),
)

match_events = sa.Table(
    "match_events",
    metadata,
    sa.Column("match_id", sa.Text, sa.ForeignKey("matches.id"), nullable=False),
    sa.Column("sequence", sa.Integer, nullable=False),
    sa.Column("event_type", sa.Text, nullable=False),
    sa.Column("timestamp", sa.Text, nullable=False),
    sa.Column("frame_index", sa.Integer, nullable=False),
    sa.Column("payload", sa.Text, nullable=False),  # JSON-encoded dict
    sa.PrimaryKeyConstraint("match_id", "sequence"),
)
