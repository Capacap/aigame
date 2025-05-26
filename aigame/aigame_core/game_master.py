# game_master.py
from __future__ import annotations
import litellm
import json # For potentially formatting parts of the prompt or if GM needs to handle complex JSON in future
from .player import Player
from .character import Character
from .scenario import Scenario # Added import for Scenario type hint
from .config import DEFAULT_LLM_MODEL, debug_llm_call
# Location might be needed if future GMs consider environment, but not for current victory condition
# from .location import Location 

from rich import print as rprint
from rich.text import Text
from rich.console import Console

console = Console()

class GameMaster:
    def __init__(self):
        # The GM could have its own personality or instructions, but for now, it's a neutral evaluator.
        pass

    def introduce_scenario(self, scenario: Scenario) -> str:
        """
        Generates an engaging introduction for the scenario using AI.
        Returns a narrative introduction string.
        """
        # Validate arguments
        if not isinstance(scenario, Scenario):
            raise ValueError("scenario must be a Scenario instance.")

        system_prompt = (
            "You are a master storyteller and Game Master. Create an engaging, atmospheric introduction "
            "for a text-based adventure scenario. The introduction should:\n"
            "- Set the scene and mood\n"
            "- Introduce the setting without being too verbose\n"
            "- Create anticipation for the adventure ahead\n"
            "- Be 2-3 sentences long\n"
            "- Use vivid but concise language\n"
            "- End with a sense of possibility or challenge\n\n"
            "Write in second person ('You find yourself...') to immerse the player."
        )

        user_prompt = (
            f"Create an introduction for this scenario:\n"
            f"Name: {scenario.name}\n"
            f"Description: {scenario.description}\n"
            f"Location: {scenario.location_name}\n"
            f"Player Character: {scenario.player_character_name}\n"
            f"NPC: {scenario.npc_character_name}"
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        debug_llm_call("GameMaster", f"Scenario introduction for {scenario.name}", DEFAULT_LLM_MODEL)

        try:
            response = litellm.completion(
                model=DEFAULT_LLM_MODEL,
                messages=messages,
                max_tokens=150,
                temperature=0.7  # More creative for narrative
            )
            return response.choices[0].message.content
        except Exception as e:
            rprint(Text(f"Error during scenario introduction: {e}", style="dim yellow"))
            return "Error generating scenario introduction."

    def analyze_and_update_disposition(self, npc: Character, player: Player, recent_events: str, scenario: Scenario = None) -> str:
        """
        Analyzes recent events and updates the NPC's disposition if warranted.
        Returns the (potentially updated) disposition.
        """
        # Validate arguments
        if not isinstance(npc, Character):
            raise ValueError("npc must be a Character instance.")
        if not isinstance(player, Player):
            raise ValueError("player must be a Player instance.")
        if not isinstance(recent_events, str) or not recent_events.strip():
            raise ValueError("recent_events must be a non-empty string.")

        # Build context for disposition analysis
        player_items_str = ", ".join(item.name for item in player.items) if player.items else "None"
        npc_items_str = ", ".join(item.name for item in npc.items) if npc.items else "None"
        
        # Enhanced system prompt with scenario context
        if scenario:
            system_prompt = (
                f"You are an expert Game Master AI analyzing character disposition changes. "
                f"Your task is to determine if recent events warrant updating an NPC's disposition "
                f"based on their personality and the scenario's victory conditions.\n\n"
                f"SCENARIO CONTEXT:\n"
                f"- Scenario: {scenario.name}\n"
                f"- Victory Condition: {scenario.victory_condition}\n"
                f"- This means the disposition should reflect how likely the NPC is to help achieve this specific goal.\n\n"
                f"CHARACTER ANALYSIS:\n"
                f"- NPC: {npc.name}\n"
                f"- Personality: {npc.personality}\n"
                f"- Goal: {npc.goal}\n"
                f"- Current Disposition: {npc.disposition}\n"
                f"- Items: [{npc_items_str}]\n\n"
                f"PLAYER CONTEXT:\n"
                f"- Player: {player.name}\n"
                f"- Items: [{player_items_str}]\n\n"
                f"DISPOSITION GUIDELINES:\n"
                f"- Disposition should reflect likelihood of helping with victory condition, not just general mood\n"
                f"- For librarians: How likely to give access to restricted materials\n"
                f"- For merchants: How favorable the trading terms might be\n"
                f"- For information holders: How willing to share secrets or keys\n"
                f"- Consider both emotional state AND practical willingness to cooperate\n\n"
                f"Examples of scenario-relevant dispositions:\n"
                f"- 'reluctantly considering the request' (moving toward cooperation)\n"
                f"- 'firmly protective of the grimoire' (resistant to giving key items)\n"
                f"- 'warming up to the customer' (merchant becoming more favorable)\n"
                f"- 'suspicious of the stranger's motives' (less likely to help)\n\n"
                f"Analyze if the recent events warrant a disposition change. "
                f"Focus on how the events affect the NPC's willingness to help achieve the victory condition. "
                f"Respond with JSON: {{'should_update': boolean, 'new_disposition': 'string', 'reasoning': 'explanation'}}"
            )
        else:
            # Fallback to original behavior if no scenario provided
            system_prompt = (
                f"You are an expert Game Master AI analyzing character disposition changes. "
                f"Your task is to determine if recent events warrant updating an NPC's disposition "
                f"based on their personality and the interaction context.\n\n"
                f"CHARACTER ANALYSIS:\n"
                f"- NPC: {npc.name}\n"
                f"- Personality: {npc.personality}\n"
                f"- Goal: {npc.goal}\n"
                f"- Current Disposition: {npc.disposition}\n"
                f"- Items: [{npc_items_str}]\n\n"
                f"PLAYER CONTEXT:\n"
                f"- Player: {player.name}\n"
                f"- Items: [{player_items_str}]\n\n"
                f"Analyze if the recent events warrant a disposition change based on the character's "
                f"personality and how they would realistically react. Consider emotional responses, "
                f"trust changes, and relationship dynamics. "
                f"Respond with JSON: {{'should_update': boolean, 'new_disposition': 'string', 'reasoning': 'explanation'}}"
            )

        user_prompt = f"Recent events to analyze: {recent_events}"

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        debug_llm_call("GameMaster", f"Disposition analysis for {npc.name}", DEFAULT_LLM_MODEL)

        try:
            response = litellm.completion(
                model=DEFAULT_LLM_MODEL,
                messages=messages,
                max_tokens=150,
                temperature=0.3,  # Some creativity but still consistent
                response_format={"type": "json_object"}
            )
            
            raw_response_content = response.choices[0].message.content
            
            if not raw_response_content:
                rprint(Text("Game Master disposition analysis returned empty response.", style="dim yellow"))
                return npc.disposition

            parsed_json = json.loads(raw_response_content)
            should_update = parsed_json.get("should_update", False)
            new_disposition = parsed_json.get("new_disposition", "")
            reasoning = parsed_json.get("reasoning", "")

            if not isinstance(should_update, bool):
                rprint(Text("Game Master disposition analysis returned invalid format.", style="dim yellow"))
                return npc.disposition

            if should_update and isinstance(new_disposition, str) and new_disposition.strip():
                old_disposition = npc.disposition
                npc.disposition = new_disposition.strip()
                
                # Game Master Analysis Section with clear separation
                console.line()
                rprint(f"🧠 [dim cyan]Game Master: {reasoning}[/dim cyan]")
                rprint(f"💭 [yellow]{npc.name}'s disposition changed: {old_disposition} → {new_disposition}[/yellow]")
                console.line()
                return new_disposition
            else:
                # No change needed
                return npc.disposition

        except json.JSONDecodeError as e:
            rprint(Text(f"Error parsing Game Master disposition analysis: {e}", style="dim yellow"))
            return npc.disposition
        except Exception as e:
            rprint(Text(f"Error during disposition analysis: {e}", style="dim yellow"))
            return npc.disposition

    def provide_epilogue(self, scenario: Scenario, player: Player, npc: Character, ending_type: str) -> str:
        """
        Generates an epilogue for the scenario based on how it ended.
        Returns a narrative epilogue string.
        """
        # Validate arguments
        if not isinstance(scenario, Scenario):
            raise ValueError("scenario must be a Scenario instance.")
        if not isinstance(player, Player):
            raise ValueError("player must be a Player instance.")
        if not isinstance(npc, Character):
            raise ValueError("npc must be a Character instance.")
        if ending_type not in ["VICTORY", "PLAYER_QUIT"]:
            raise ValueError("ending_type must be 'VICTORY' or 'PLAYER_QUIT'.")

        player_items_str = ", ".join(item.name for item in player.items) if player.items else "None"
        npc_items_str = ", ".join(item.name for item in npc.items) if npc.items else "None"

        system_prompt = (
            "You are a master storyteller providing an epilogue for a completed adventure. "
            "Create a satisfying conclusion that:\n"
            "- Reflects the outcome of the adventure\n"
            "- Acknowledges the character relationships that developed\n"
            "- Provides closure to the story\n"
            "- Is 2-3 sentences long\n"
            "- Matches the tone of the ending (triumphant for victory, reflective for quitting)\n\n"
            "Write in a narrative style that wraps up the adventure."
        )

        if ending_type == "VICTORY":
            user_prompt = (
                f"Create a victory epilogue for:\n"
                f"Scenario: {scenario.name}\n"
                f"Player: {player.name} (final items: {player_items_str})\n"
                f"NPC: {npc.name} (final disposition: {npc.disposition}, final items: {npc_items_str})\n"
                f"Victory Condition: {scenario.victory_condition}\n\n"
                f"The player successfully achieved their goal. Celebrate their success and the relationship they built."
            )
        else:  # PLAYER_QUIT
            user_prompt = (
                f"Create a reflective epilogue for:\n"
                f"Scenario: {scenario.name}\n"
                f"Player: {player.name} (final items: {player_items_str})\n"
                f"NPC: {npc.name} (final disposition: {npc.disposition}, final items: {npc_items_str})\n\n"
                f"The player chose to end their adventure early. Reflect on the journey and leave the door open for future possibilities."
            )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        debug_llm_call("GameMaster", f"Epilogue generation ({ending_type})", DEFAULT_LLM_MODEL)

        try:
            response = litellm.completion(
                model=DEFAULT_LLM_MODEL,
                messages=messages,
                max_tokens=120,
                temperature=0.7  # Creative for narrative
            )
            return response.choices[0].message.content
        except Exception as e:
            rprint(Text(f"Error during epilogue generation: {e}", style="dim yellow"))
            return "Error generating epilogue."

    def _format_state_for_llm(self, player: Player, npc: Character, victory_condition: str) -> str:
        player_items_str = ", ".join(item.name for item in player.items) if player.items else "None"
        npc_items_str = ", ".join(item.name for item in npc.items) if npc.items else "None"
        
        state_description = (
            f"Current Game State:\n"
            f"- Player: {player.name}\n  - Items: [{player_items_str}]\n"
            f"- NPC: {npc.name}\n  - Items: [{npc_items_str}]\n  - Disposition: {npc.disposition}\n"
            f"\nVictory Condition to Evaluate:\n{victory_condition}"
        )
        return state_description

    def evaluate_victory_condition(self, player: Player, npc: Character, victory_condition: str) -> tuple[bool, str]:
        """
        Uses an LLM to evaluate if the victory condition has been met.
        Returns a tuple of (is_met: bool, reasoning: str)
        """
        state_prompt = self._format_state_for_llm(player, npc, victory_condition)

        system_message = (
            "You are a meticulous Game Master AI. Your task is to evaluate if a specific victory condition "
            "has been met based on the current game state provided. "
            "You must provide both a clear determination (true/false) and a brief explanation of your reasoning. "
            "Be precise and factual in your analysis. "
            "Respond with a JSON object containing two keys: "
            "'result' (boolean: true if condition is met, false if not) and "
            "'reasoning' (string: 1-2 sentence explanation of why the condition is or isn't met)."
        )
        
        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": state_prompt + "\n\nEvaluate this victory condition based strictly on the current game state. Provide your response as a JSON object."}
        ]

        debug_llm_call("GameMaster", "Victory condition evaluation", DEFAULT_LLM_MODEL)

        try:
            response = litellm.completion(
                model=DEFAULT_LLM_MODEL,
                messages=messages,
                max_tokens=100, # Allow more tokens for reasoning
                temperature=0.0, # We want deterministic evaluation
                response_format={"type": "json_object"}
            )
            raw_response_content = response.choices[0].message.content
            
            if not raw_response_content:
                return False, "Game Master evaluation failed - empty response."

            try:
                parsed_json = json.loads(raw_response_content)
                result = parsed_json.get("result", False)
                reasoning = parsed_json.get("reasoning", "No reasoning provided.")
                
                if not isinstance(result, bool):
                    return False, "Game Master evaluation failed - invalid result format."
                
                return result, reasoning
                
            except json.JSONDecodeError as e:
                rprint(Text(f"[bold red]Error parsing Game Master response: {e}[/bold red]"))
                return False, f"Game Master evaluation failed - JSON parsing error: {str(e)}"

        except Exception as e:
            rprint(Text(f"[bold red]Error during Game Master AI evaluation: {e}[/bold red]"))
            return False, f"Game Master evaluation failed - {str(e)}"

    def parse_trade_proposal(
        self,
        player: Player,
        npc: Character,
        trade_message: str
    ) -> tuple[bool, str, str, str]:
        """
        Uses an LLM to parse a trade proposal message and extract the items involved.
        Returns (is_valid_trade, player_item_name, npc_item_name, reason)
        """
        # Validate arguments
        if not isinstance(player, Player):
            raise ValueError("player must be a Player instance.")
        if not isinstance(npc, Character):
            raise ValueError("npc must be a Character instance.")
        if not isinstance(trade_message, str) or not trade_message.strip():
            raise ValueError("trade_message must be a non-empty string.")

        player_items_str = ", ".join(item.name for item in player.items) if player.items else "None"
        npc_items_str = ", ".join(item.name for item in npc.items) if npc.items else "None"

        system_prompt = (
            f"You are a trade proposal parser. Analyze the player's message to determine if it contains "
            f"a valid trade proposal (offering one of their items for one of the NPC's items).\n\n"
            f"Available items:\n"
            f"- Player has: [{player_items_str}]\n"
            f"- NPC has: [{npc_items_str}]\n\n"
            f"A valid trade proposal must:\n"
            f"1. Clearly indicate the player wants to trade/exchange items\n"
            f"2. Specify one item the player is offering (must be from their inventory)\n"
            f"3. Specify one item they want from the NPC (must be from NPC's inventory)\n\n"
            f"Respond with JSON containing:\n"
            f"- 'is_valid_trade': boolean (true if this is a valid trade proposal)\n"
            f"- 'player_item_name': string (exact name of item player is offering, or empty if invalid)\n"
            f"- 'npc_item_name': string (exact name of item player wants from NPC, or empty if invalid)\n"
            f"- 'reason': string (brief explanation of your decision)"
        )

        user_prompt = f"Player message to analyze: \"{trade_message}\""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        debug_llm_call("GameMaster", "Trade proposal parsing", DEFAULT_LLM_MODEL)

        try:
            response = litellm.completion(
                model=DEFAULT_LLM_MODEL,
                messages=messages,
                temperature=0.1, # Low temperature for precise parsing
                response_format={"type": "json_object"}
            )
            raw_response_content = response.choices[0].message.content
            
            if not raw_response_content:
                rprint(Text("GM Trade Parser returned empty response. Treating as invalid trade.", style="dim yellow"))
                return False, "", "", "Failed to parse trade proposal."

            parsed_json = json.loads(raw_response_content)

            is_valid_trade = parsed_json.get("is_valid_trade", False)
            player_item_name = parsed_json.get("player_item_name", "")
            npc_item_name = parsed_json.get("npc_item_name", "")
            reason = parsed_json.get("reason", "")

            if not isinstance(is_valid_trade, bool):
                rprint(Text(f"GM Trade Parser: 'is_valid_trade' is not a boolean. Treating as invalid. JSON: {parsed_json}", style="red"))
                return False, "", "", "Invalid response format from trade parser."
            
            if is_valid_trade:
                if not isinstance(player_item_name, str) or not player_item_name:
                    rprint(Text(f"GM Trade Parser: Valid trade but 'player_item_name' is invalid. JSON: {parsed_json}", style="red"))
                    return False, "", "", "Could not identify player's item in trade proposal."
                
                if not isinstance(npc_item_name, str) or not npc_item_name:
                    rprint(Text(f"GM Trade Parser: Valid trade but 'npc_item_name' is invalid. JSON: {parsed_json}", style="red"))
                    return False, "", "", "Could not identify NPC's item in trade proposal."
                
                # Verify the items actually exist in the inventories
                if not player.has_item(player_item_name):
                    return False, "", "", f"Player does not have '{player_item_name}' to trade."
                
                if not npc.has_item(npc_item_name):
                    return False, "", "", f"NPC does not have '{npc_item_name}' to trade."

            return is_valid_trade, player_item_name if is_valid_trade else "", npc_item_name if is_valid_trade else "", reason

        except json.JSONDecodeError as e:
            rprint(Text(f"[bold red]Error decoding JSON from GM Trade Parser: {e}. Raw: '{raw_response_content}'. Treating as invalid trade.[/bold red]"))
            return False, "", "", "Failed to parse trade proposal due to JSON error."
        except Exception as e:
            rprint(Text(f"[bold red]Error during GM Trade Parsing: {e}. Treating as invalid trade.[/bold red]"))
            return False, "", "", f"Error parsing trade proposal: {str(e)}" 