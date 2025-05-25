# game_master.py
from __future__ import annotations
import litellm
import json # For potentially formatting parts of the prompt or if GM needs to handle complex JSON in future
from .player import Player
from .character import Character
from .scenario import Scenario # Added import for Scenario type hint
from .config import DEFAULT_LLM_MODEL
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
        """Generates an introductory narration for the given scenario."""
        if not isinstance(scenario, Scenario):
            raise ValueError("Invalid scenario object provided to introduce_scenario.")
        
        # For now, a simple formatted introduction. This could be expanded.
        # Using f-string for clarity and rich Text for potential future styling within the string.
        intro_text = (
            f"Welcome, adventurer, to \"{scenario.name}\"!\n\n"
            f"{scenario.description}"
        )
        return intro_text

    def analyze_and_update_disposition(self, npc: Character, player: Player, recent_events: str) -> str:
        """
        Analyzes recent events and updates the NPC's disposition accordingly.
        Returns the new disposition as a natural language prompt.
        """
        # Validate arguments
        if not isinstance(npc, Character):
            raise ValueError("Invalid NPC character object provided.")
        if not isinstance(player, Player):
            raise ValueError("Invalid player object provided.")
        if not isinstance(recent_events, str) or not recent_events.strip():
            raise ValueError("Recent events must be a non-empty string.")

        try:
            # Get current state for context
            current_disposition = npc.disposition
            npc_items = ", ".join(item.name for item in npc.items) if npc.items else "None"
            player_items = ", ".join(item.name for item in player.items) if player.items else "None"
            
            # Get recent conversation history for additional context
            recent_history = npc.interaction_history.get_llm_history()
            conversation_context = ""
            if recent_history:
                # Get last few exchanges for context
                last_exchanges = recent_history[-4:] if len(recent_history) > 4 else recent_history
                for entry in last_exchanges:
                    role_name = player.name if entry["role"] == "user" else npc.name
                    conversation_context += f"{role_name}: {entry.get('content', '')}\n"

            system_message = (
                f"You are a Game Master AI analyzing how recent events should affect an NPC's disposition. "
                f"Your task is to determine if the NPC's current disposition should change based on what just happened. "
                f"Consider the NPC's personality, goals, and how they would realistically react to the recent events. "
                f"The disposition should be a natural language description of the NPC's current emotional state, "
                f"attitude, or mindset that will guide their future responses. "
                f"Examples: 'suspicious and guarded', 'grateful and friendly', 'angry and hostile', "
                f"'curious but cautious', 'impressed and respectful', 'disappointed but hopeful'. "
                f"Only change the disposition if the events warrant a meaningful shift. "
                f"Respond with a JSON object containing: "
                f"'should_update' (boolean), 'new_disposition' (string), and 'reasoning' (string)."
            )

            user_prompt = (
                f"NPC: {npc.name}\n"
                f"Personality: {npc.personality}\n"
                f"Goal: {npc.goal}\n"
                f"Current Disposition: {current_disposition}\n"
                f"NPC Items: {npc_items}\n"
                f"Player Items: {player_items}\n\n"
                f"Recent Events:\n{recent_events}\n\n"
                f"Recent Conversation Context:\n{conversation_context}\n"
                f"Based on the NPC's personality and the recent events, should their disposition change? "
                f"If so, what should the new disposition be?"
            )

            messages = [
                {"role": "system", "content": system_message},
                {"role": "user", "content": user_prompt}
            ]

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

    def provide_epilogue(self, scenario: Scenario, player: Player, npc: Character, game_outcome: str) -> str:
        """Generates a concluding narration for the scenario based on the outcome."""
        if not isinstance(scenario, Scenario):
            raise ValueError("Invalid scenario object provided to provide_epilogue.")
        if not isinstance(player, Player):
            raise ValueError("Invalid player object provided to provide_epilogue.")
        if not isinstance(npc, Character):
            raise ValueError("Invalid NPC object provided to provide_epilogue.")
        if not isinstance(game_outcome, str) or not game_outcome:
            raise ValueError("Game outcome must be a non-empty string.")

        epilogue_text = f"Thus concludes \"{scenario.name}\".\n\n"

        if game_outcome == "VICTORY":
            epilogue_text += f"Through skill and determination, {player.name} successfully achieved the objective! "
            epilogue_text += f"{npc.name} is now {npc.disposition}. " 
            epilogue_text += "\nA chapter closes, but the story continues..."
        elif game_outcome == "PLAYER_QUIT":
            epilogue_text += f"{player.name} decided to walk away from this particular path. "
            epilogue_text += f"The threads of fate remain untangled, and {npc.name} is left to ponder what might have been, their disposition {npc.disposition}. "
            epilogue_text += "Perhaps another time, another place?"
        else:
            epilogue_text += "The story ends, but its echoes linger..."
        
        return epilogue_text

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
        Parses a natural language trade proposal to extract item names.
        Returns a tuple: (is_valid_trade: bool, player_item_name: str, npc_item_name: str, reason: str)
        Empty strings for item names and reason if is_valid_trade is False.
        """
        if not isinstance(player, Player):
            raise ValueError("Invalid player object provided.")
        if not isinstance(npc, Character):
            raise ValueError("Invalid NPC object provided.")
        if not isinstance(trade_message, str) or not trade_message.strip():
            return False, "", "", "Trade message cannot be empty."

        # Get available items for context
        player_items_str = ", ".join(f"'{item.name}'" for item in player.items) if player.items else "None"
        npc_items_str = ", ".join(f"'{item.name}'" for item in npc.items) if npc.items else "None"

        system_prompt = (
            "You are a Game Master AI specialized in parsing trade proposals. Your task is to analyze "
            "a player's natural language trade message and extract the specific item names being proposed for trade. "
            "The player wants to trade one of their items for one of the NPC's items. "
            "Look for phrases like 'I offer my X for your Y', 'trade my X for your Y', 'exchange my X for your Y', etc. "
            "Extract the EXACT item names as they appear in the available inventories. "
            "Be flexible with case sensitivity and partial matches - if the player says 'bag of coins' and the inventory has 'Bag of Coins', that's a match. "
            "Similarly, 'cypher' should match 'translation cypher', 'amulet' should match 'Ancient Amulet', 'key' should match 'Echo Chamber Key', etc. "
            "Use your best judgment to match player descriptions to actual item names, but be conservative - only match if you're confident. "
            "If the message doesn't clearly propose a trade between specific items, or if you can't confidently match the mentioned items "
            "to the available inventories, mark it as invalid. "
            "Respond ONLY with a JSON object with four keys: "
            "'is_valid_trade' (boolean), 'player_item_name' (string, exact name from player inventory), "
            "'npc_item_name' (string, exact name from NPC inventory), and 'reason' (string, explanation)."
        )

        user_prompt = (
            f"Player ({player.name}) available items: [{player_items_str}]\n"
            f"NPC ({npc.name}) available items: [{npc_items_str}]\n\n"
            f"Player's trade message: \"{trade_message}\"\n\n"
            "Parse this message to extract the trade proposal. What item is the player offering, "
            "and what item do they want in return? Provide your response as a JSON object."
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

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