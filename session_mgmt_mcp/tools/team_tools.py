#!/usr/bin/env python3
"""Team collaboration tools for session-mgmt-mcp.

Following crackerjack architecture patterns for knowledge sharing,
team coordination, and collaborative development workflows.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def register_team_tools(mcp) -> None:
    """Register all team collaboration MCP tools.

    Args:
        mcp: FastMCP server instance

    """

    @mcp.tool()
    async def create_team_user(
        user_id: str,
        username: str,
        role: str = "contributor",
        email: str | None = None,
    ) -> str:
        """Create a new team user with specified role."""
        try:
            from session_mgmt_mcp.team_knowledge import TeamKnowledgeManager

            manager = TeamKnowledgeManager()
            await manager.create_user(
                user_id=user_id,
                username=username,
                role=role,
                email=email,
            )

            return f"✅ Team user created successfully: {username} ({role})"

        except ImportError:
            logger.warning("Team knowledge system not available")
            return "❌ Team collaboration features not available. Install optional dependencies."
        except Exception as e:
            logger.exception(f"Team user creation failed: {e}")
            return f"❌ Failed to create team user: {e!s}"

    @mcp.tool()
    async def create_team(
        team_id: str, name: str, description: str, owner_id: str
    ) -> str:
        """Create a new team for knowledge sharing."""
        try:
            from session_mgmt_mcp.team_knowledge import TeamKnowledgeManager

            manager = TeamKnowledgeManager()
            await manager.create_team(
                team_id=team_id,
                name=name,
                description=description,
                owner_id=owner_id,
            )

            return f"✅ Team created successfully: {name}"

        except ImportError:
            logger.warning("Team knowledge system not available")
            return "❌ Team collaboration features not available. Install optional dependencies."
        except Exception as e:
            logger.exception(f"Team creation failed: {e}")
            return f"❌ Failed to create team: {e!s}"

    @mcp.tool()
    async def add_team_reflection(
        content: str,
        author_id: str,
        team_id: str | None = None,
        project_id: str | None = None,
        tags: list[str] | None = None,
        access_level: str = "team",
    ) -> str:
        """Add reflection to team knowledge base with access control."""
        try:
            from session_mgmt_mcp.team_knowledge import TeamKnowledgeManager

            manager = TeamKnowledgeManager()
            reflection_id = await manager.add_reflection(
                content=content,
                author_id=author_id,
                team_id=team_id,
                project_id=project_id,
                tags=tags or [],
                access_level=access_level,
            )

            output = f"✅ Team reflection added successfully (ID: {reflection_id})\n"

            if team_id:
                output += f"📋 Team: {team_id}\n"
            if project_id:
                output += f"🏗️ Project: {project_id}\n"
            if tags:
                output += f"🏷️ Tags: {', '.join(tags)}\n"
            output += f"🔐 Access: {access_level}"

            return output

        except ImportError:
            logger.warning("Team knowledge system not available")
            return "❌ Team collaboration features not available. Install optional dependencies."
        except Exception as e:
            logger.exception(f"Team reflection addition failed: {e}")
            return f"❌ Failed to add team reflection: {e!s}"

    @mcp.tool()
    async def search_team_knowledge(
        query: str,
        user_id: str,
        team_id: str | None = None,
        project_id: str | None = None,
        tags: list[str] | None = None,
        limit: int = 20,
    ) -> str:
        """Search team reflections with access control."""
        try:
            from session_mgmt_mcp.team_knowledge import TeamKnowledgeManager

            manager = TeamKnowledgeManager()
            results = await manager.search_knowledge(
                query=query,
                user_id=user_id,
                team_id=team_id,
                project_id=project_id,
                tags=tags,
                limit=limit,
            )

            if not results:
                search_scope = "team knowledge"
                if team_id:
                    search_scope += f" (team: {team_id})"
                if project_id:
                    search_scope += f" (project: {project_id})"
                return f"🔍 No results found in {search_scope} for: {query}"

            output = f"🔍 **{len(results)} team knowledge results** for '{query}'\n\n"

            for i, result in enumerate(results, 1):
                output += f"**{i}.** "

                # Add metadata
                if result.get("team_id"):
                    output += f"[{result['team_id']}] "
                if result.get("author"):
                    output += f"by {result['author']} "
                if result.get("timestamp"):
                    output += f"({result['timestamp']}) "

                # Add content preview
                content = result.get("content", "")
                output += f"\n{content[:200]}...\n"

                # Add tags if available
                if result.get("tags"):
                    output += f"🏷️ Tags: {', '.join(result['tags'])}\n"

                # Add voting info if available
                if result.get("votes"):
                    votes = result["votes"]
                    output += f"👍 Votes: {votes} "

                output += "\n"

            return output

        except ImportError:
            logger.warning("Team knowledge system not available")
            return "❌ Team collaboration features not available. Install optional dependencies."
        except Exception as e:
            logger.exception(f"Team knowledge search failed: {e}")
            return f"❌ Team knowledge search failed: {e!s}"

    @mcp.tool()
    async def join_team(
        user_id: str, team_id: str, requester_id: str | None = None
    ) -> str:
        """Join a team or add user to team."""
        try:
            from session_mgmt_mcp.team_knowledge import TeamKnowledgeManager

            manager = TeamKnowledgeManager()
            await manager.join_team(
                user_id=user_id,
                team_id=team_id,
                requester_id=requester_id,
            )

            if requester_id and requester_id != user_id:
                return f"✅ User {user_id} added to team {team_id} by {requester_id}"
            return f"✅ Successfully joined team: {team_id}"

        except ImportError:
            logger.warning("Team knowledge system not available")
            return "❌ Team collaboration features not available. Install optional dependencies."
        except Exception as e:
            logger.exception(f"Team join failed: {e}")
            return f"❌ Failed to join team: {e!s}"

    @mcp.tool()
    async def get_team_statistics(team_id: str, user_id: str) -> str:
        """Get team statistics and activity."""
        try:
            from session_mgmt_mcp.team_knowledge import TeamKnowledgeManager

            manager = TeamKnowledgeManager()
            stats = await manager.get_team_stats(team_id=team_id, user_id=user_id)

            output = f"📊 **Team Statistics: {team_id}**\n\n"

            # Basic stats
            output += f"**Members**: {stats.get('member_count', 0)}\n"
            output += f"**Reflections**: {stats.get('reflection_count', 0)}\n"
            output += f"**Projects**: {stats.get('project_count', 0)}\n"
            output += f"**Total Votes**: {stats.get('total_votes', 0)}\n\n"

            # Activity stats
            if stats.get("recent_activity"):
                output += "**Recent Activity**:\n"
                for activity in stats["recent_activity"][:5]:
                    output += f"- {activity.get('timestamp', '')}: {activity.get('description', '')}\n"

            # Top contributors
            if stats.get("top_contributors"):
                output += "\n**Top Contributors**:\n"
                for contributor in stats["top_contributors"][:5]:
                    output += f"- {contributor.get('username', '')}: {contributor.get('contributions', 0)} contributions\n"

            # Popular tags
            if stats.get("popular_tags"):
                output += (
                    f"\n**Popular Tags**: {', '.join(stats['popular_tags'][:10])}\n"
                )

            return output

        except ImportError:
            logger.warning("Team knowledge system not available")
            return "❌ Team collaboration features not available. Install optional dependencies."
        except Exception as e:
            logger.exception(f"Team statistics failed: {e}")
            return f"❌ Failed to get team statistics: {e!s}"

    @mcp.tool()
    async def get_user_team_permissions(user_id: str) -> str:
        """Get user's permissions and team memberships."""
        try:
            from session_mgmt_mcp.team_knowledge import TeamKnowledgeManager

            manager = TeamKnowledgeManager()
            permissions = await manager.get_user_permissions(user_id=user_id)

            output = f"🔐 **User Permissions: {user_id}**\n\n"

            # Team memberships
            teams = permissions.get("teams", [])
            if teams:
                output += "**Team Memberships**:\n"
                for team in teams:
                    team_name = team.get("name", team.get("team_id", "Unknown"))
                    role = team.get("role", "member")
                    output += f"- {team_name} ({role})\n"
            else:
                output += "**Team Memberships**: None\n"

            # Permissions
            perms = permissions.get("permissions", {})
            output += "\n**Permissions**:\n"
            output += f"- Can create teams: {perms.get('can_create_teams', False)}\n"
            output += (
                f"- Can add reflections: {perms.get('can_add_reflections', True)}\n"
            )
            output += f"- Can vote: {perms.get('can_vote', True)}\n"
            output += f"- Can moderate: {perms.get('can_moderate', False)}\n"

            # Statistics
            stats = permissions.get("stats", {})
            if stats:
                output += "\n**User Statistics**:\n"
                output += (
                    f"- Total reflections: {stats.get('reflections_created', 0)}\n"
                )
                output += f"- Total votes cast: {stats.get('votes_cast', 0)}\n"
                output += f"- Teams joined: {len(teams)}\n"

            return output

        except ImportError:
            logger.warning("Team knowledge system not available")
            return "❌ Team collaboration features not available. Install optional dependencies."
        except Exception as e:
            logger.exception(f"User permissions check failed: {e}")
            return f"❌ Failed to get user permissions: {e!s}"

    @mcp.tool()
    async def vote_on_reflection(
        reflection_id: str,
        user_id: str,
        vote_delta: int = 1,
    ) -> str:
        """Vote on a team reflection (upvote/downvote)."""
        try:
            from session_mgmt_mcp.team_knowledge import TeamKnowledgeManager

            manager = TeamKnowledgeManager()
            result = await manager.vote_on_reflection(
                reflection_id=reflection_id,
                user_id=user_id,
                vote_delta=vote_delta,
            )

            vote_action = (
                "upvoted"
                if vote_delta > 0
                else "downvoted"
                if vote_delta < 0
                else "neutral"
            )
            new_score = result.get("new_score", 0)

            output = f"✅ Reflection {vote_action} successfully\n"
            output += f"📊 New vote score: {new_score}\n"

            if result.get("previous_vote"):
                output += "ℹ️ Updated previous vote"
            else:
                output += "ℹ️ First vote on this reflection"

            return output

        except ImportError:
            logger.warning("Team knowledge system not available")
            return "❌ Team collaboration features not available. Install optional dependencies."
        except ValueError as e:
            return f"❌ Vote failed: {e!s}"
        except Exception as e:
            logger.exception(f"Voting failed: {e}")
            return f"❌ Failed to vote on reflection: {e!s}"

    # Additional team utility tools
    @mcp.tool()
    async def list_team_projects(team_id: str, user_id: str) -> str:
        """List projects associated with a team."""
        try:
            from session_mgmt_mcp.team_knowledge import TeamKnowledgeManager

            manager = TeamKnowledgeManager()
            projects = await manager.get_team_projects(team_id=team_id, user_id=user_id)

            if not projects:
                return f"📁 No projects found for team: {team_id}"

            output = f"📁 **Projects for team: {team_id}**\n\n"

            for i, project in enumerate(projects, 1):
                output += f"**{i}.** {project.get('name', project.get('project_id', 'Unknown'))}\n"

                if project.get("description"):
                    output += f"   Description: {project['description']}\n"

                if project.get("reflection_count"):
                    output += f"   Reflections: {project['reflection_count']}\n"

                if project.get("last_activity"):
                    output += f"   Last activity: {project['last_activity']}\n"

                output += "\n"

            return output

        except ImportError:
            logger.warning("Team knowledge system not available")
            return "❌ Team collaboration features not available. Install optional dependencies."
        except Exception as e:
            logger.exception(f"Project listing failed: {e}")
            return f"❌ Failed to list team projects: {e!s}"

    @mcp.tool()
    async def get_team_activity_feed(
        team_id: str, user_id: str, limit: int = 20
    ) -> str:
        """Get recent activity feed for a team."""
        try:
            from session_mgmt_mcp.team_knowledge import TeamKnowledgeManager

            manager = TeamKnowledgeManager()
            activities = await manager.get_activity_feed(
                team_id=team_id,
                user_id=user_id,
                limit=limit,
            )

            if not activities:
                return f"📰 No recent activity for team: {team_id}"

            output = f"📰 **Activity Feed: {team_id}**\n\n"

            for activity in activities:
                timestamp = activity.get("timestamp", "")
                actor = activity.get("actor", "Unknown")
                action = activity.get("action", "")
                target = activity.get("target", "")

                output += f"**{timestamp}** - {actor} {action}"
                if target:
                    output += f" {target}"
                output += "\n"

                if activity.get("details"):
                    output += f"   {activity['details']}\n"
                output += "\n"

            return output

        except ImportError:
            logger.warning("Team knowledge system not available")
            return "❌ Team collaboration features not available. Install optional dependencies."
        except Exception as e:
            logger.exception(f"Activity feed failed: {e}")
            return f"❌ Failed to get activity feed: {e!s}"
