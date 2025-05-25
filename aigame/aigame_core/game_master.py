# game_master.py
from __future__ import annotations
import litellm
import json # For potentially formatting parts of the prompt or if GM needs to handle complex JSON in future
from .player import Player
from .character import Character
from .scenario import Scenario # Added import for Scenario type hint
# Location might be needed if future GMs consider environment, but not for current victory condition
# from .location import Location 

from rich import print as rprint
from rich.text import Text

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
            # Could add more details based on victory condition, player/npc items, npc disposition etc.
            epilogue_text += f"{npc.name} is now {npc.disposition}. " 
            # Check if the victory involved obtaining an item
            vc = scenario.victory_condition
            if vc.get("type") == "PLAYER_OBTAINS_ITEM" and vc.get("item_name"):
                epilogue_text += f"{player.name} is now in possession of the coveted {vc.get("item_name")}."
            epilogue_text += "\nA chapter closes, but the story continues..."
        elif game_outcome == "PLAYER_QUIT":
            epilogue_text += f"{player.name} decided to walk away from this particular path. "
            epilogue_text += f"The threads of fate remain untangled, and {npc.name} is left to ponder what might have been, their disposition {npc.disposition}. "
            epilogue_text += "Perhaps another time, another place?"
        else:
            epilogue_text += "The story ends, but its echoes linger..."
        
        return epilogue_text

    def _format_state_for_llm(self, player: Player, npc: Character, victory_condition: dict) -> str:
        player_items_str = ", ".join(item.name for item in player.items) if player.items else "None"
        npc_items_str = ", ".join(item.name for item in npc.items) if npc.items else "None"
        
        # Describe the victory condition clearly
        vc_type = victory_condition.get("type")
        vc_item_name = victory_condition.get("item_name")
        vc_from_npc = victory_condition.get("from_npc", False)

        vc_description = "Unknown victory condition."
        if vc_type == "PLAYER_OBTAINS_ITEM":
            vc_description = f"The player ('{player.name}') must possess the item '{vc_item_name}'."
            if vc_from_npc:
                vc_description += f" Additionally, the NPC ('{npc.name}') must no longer possess this item."
        # Future victory condition descriptions can be added here

        state_description = (
            f"Current Game State:\n"
            f"- Player: {player.name}\n  - Items: [{player_items_str}]\n"
            f"- NPC: {npc.name}\n  - Items: [{npc_items_str}]\n  - Disposition: {npc.disposition}\n"
            f"\nVictory Condition to Evaluate:\n{vc_description}"
        )
        return state_description

    def evaluate_victory_condition(
        self, 
        player: Player, 
        npc: Character, 
        # current_location: Location, # Not strictly needed for current VC, but good for future GM tasks
        victory_condition: dict
    ) -> bool:
        """
        Uses an LLM to evaluate if the victory condition has been met.
        """
        state_prompt = self._format_state_for_llm(player, npc, victory_condition)

        system_message = (
            "You are a meticulous Game Master AI. Your sole task is to evaluate if a specific, predefined "
            "victory condition has been met based on the current game state provided. "
            "Do not offer opinions, suggestions, or any narrative. "
            "Consider only the facts presented against the victory condition. "
            "Respond with only the word 'true' if the condition is met, or 'false' if it is not."
        )
        
        messages = [
            {"role": "system", "content": system_message},
            {"role": "user", "content": state_prompt + "\n\nHas this victory condition been met based *strictly* on the rules and state provided? (Respond with only 'true' or 'false')"}
        ]

        try:
            # rprint(f"[grey50]GM Prompt to LLM:\nSystem: {system_message}\nUser: {messages[1]['content']}[/grey50]") # For debugging
            response = litellm.completion(
                model="openai/gpt-4.1-mini", # Or another suitable model
                messages=messages,
                max_tokens=5, # Should only need 'true' or 'false'
                temperature=0.0 # We want deterministic evaluation
            )
            raw_response_content = response.choices[0].message.content.strip().lower()
            rprint(Text(f"GM AI raw evaluation: '{raw_response_content}'", style="dim yellow"))

            if raw_response_content == "true":
                return True
            elif raw_response_content == "false":
                return False
            else:
                rprint(Text(f"[bold red]GM AI returned an unexpected response: '{raw_response_content}'. Defaulting to false.[/bold red]"))
                return False

        except Exception as e:
            rprint(Text(f"[bold red]Error during Game Master AI evaluation: {e}. Defaulting to false.[/bold red]"))
            return False 

    def assess_disposition_change(
        self,
        player: Player, 
        npc: Character,
        player_message: str,
        npc_response: str | None
    ) -> tuple[bool, str, str]:
        """
        Assesses if the NPC's disposition should change based on the last interaction turn.
        Returns a tuple: (should_change: bool, new_disposition: str, reason: str)
        An empty string for new_disposition and reason if should_change is False.
        """
        if not isinstance(player, Player):
            raise ValueError("Invalid player object provided.")
        if not isinstance(npc, Character):
            raise ValueError("Invalid NPC object provided.")
        if not isinstance(player_message, str):
            # Allow empty if it was a non-dialogue action, though context might be less clear for GM
            player_message = "[Player performed an action or said nothing]" if not player_message else player_message
        # npc_response can be None if AI chose to be silent or errored

        npc_details = (
            f"NPC Name: {npc.name}\n"
            f"NPC Personality: {npc.personality}\n"
            f"NPC Current Goal: {npc.goal}\n"
            f"NPC Current Disposition: {npc.disposition}"
        )

        interaction_summary = (
            f"Last interaction turn:\n"
            f"{player.name} (Player) said: \"{player_message}\"\n"
            f"{npc.name} (NPC) responded: \"{npc_response if npc_response else '[NPC gave no verbal response]'}\""
        )

        system_prompt = (
            "You are an impartial Game Master AI. Your task is to analyze the last interaction turn "
            "between a player and an NPC, considering the NPC's personality, goals, and current disposition. "
            "Based on this, decide if the NPC's disposition should realistically change, either positively or negatively. "
            "Consider factors like politeness, rudeness, alignment with NPC goals, helpfulness, threats, etc. "
            "A single neutral or mildly impolite/polite comment might not be enough unless the NPC is particularly sensitive or the comment is very impactful. Sustained behavior or very strong single interactions are more likely to cause a change."
            "If a change is warranted, suggest a new, concise disposition (e.g., 'more friendly', 'slightly annoyed', 'distrustful and wary', 'grateful', 'intrigued', 'offended'). "
            "Provide a brief reason for this change directly reflecting the interaction and NPC traits."
            "Respond ONLY with a JSON object with three keys: 'should_change' (boolean), 'new_disposition' (string, or empty if no change), and 'reason' (string, or empty if no change)."
            "Example 1 (No Change): {\"should_change\": false, \"new_disposition\": \"\", \"reason\": \"\"}"
            "Example 2 (Positive Change): {\"should_change\": true, \"new_disposition\": \"more trusting and friendly\", \"reason\": \"Player was respectful and offered help aligning with NPC goal.\"}"
            "Example 3 (Negative Change): {\"should_change\": true, \"new_disposition\": \"irritated and suspicious\", \"reason\": \"Player was very rude and dismissive of the NPC\'s prized possession.\"}"
        )

        user_prompt = (
            f"{npc_details}\n\n"
            f"{interaction_summary}\n\n"
            "Based on all the above, should the NPC's disposition change? Provide your response as a JSON object as specified."
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        try:
            # For debugging GM disposition prompt:
            # rprint(f"[grey30]GM Disposition Prompt to LLM:\nSystem: {system_prompt}\nUser: {user_prompt}[/grey30]")
            
            response = litellm.completion(
                model="openai/gpt-4.1-mini",
                messages=messages,
                temperature=0.2, # Slightly creative but mostly factual
                response_format={"type": "json_object"} # Request JSON output
            )
            raw_response_content = response.choices[0].message.content
            
            if not raw_response_content:
                rprint(Text("GM Disposition AI returned empty response. Assuming no change.", style="dim yellow"))
                return False, "", ""

            #rprint(Text(f"GM Disposition AI raw JSON: '{raw_response_content}'", style="dim yellow")) # Debug
            parsed_json = json.loads(raw_response_content)

            should_change = parsed_json.get("should_change", False)
            new_disposition = parsed_json.get("new_disposition", "")
            reason = parsed_json.get("reason", "")

            if not isinstance(should_change, bool):
                rprint(Text(f"GM Disposition AI: 'should_change' is not a boolean. Defaulting to False. JSON: {parsed_json}", style="red"))
                return False, "", ""
            if should_change and (not isinstance(new_disposition, str) or not new_disposition):
                rprint(Text(f"GM Disposition AI: 'should_change' is True but 'new_disposition' is invalid. Reverting to no change. JSON: {parsed_json}", style="red"))
                return False, "", ""
            if should_change and (not isinstance(reason, str) or not reason):
                 rprint(Text(f"GM Disposition AI: 'should_change' is True but 'reason' is invalid. Using default reason. JSON: {parsed_json}", style="yellow"))
                 reason = "GM determined a change was warranted based on the interaction."

            return should_change, new_disposition if should_change else "", reason if should_change else ""

        except json.JSONDecodeError as e:
            rprint(Text(f"[bold red]Error decoding JSON from GM Disposition AI: {e}. Raw: '{raw_response_content}'. Defaulting to no change.[/bold red]"))
            return False, "", ""
        except Exception as e:
            rprint(Text(f"[bold red]Error during GM Disposition AI assessment: {e}. Defaulting to no change.[/bold red]"))
            return False, "", "" 

    def assess_narrative_direction(
        self,
        player: Player,
        npc: Character,
        scenario: Scenario,
        player_message: str,
        npc_response: str | None,
        victory_condition: dict
    ) -> tuple[bool, str, str]:
        """
        Assesses if the NPC should receive new narrative direction based on the current story state.
        Returns a tuple: (should_provide_direction: bool, new_direction: str, reason: str)
        Empty strings for new_direction and reason if should_provide_direction is False.
        """
        if not isinstance(player, Player):
            raise ValueError("Invalid player object provided.")
        if not isinstance(npc, Character):
            raise ValueError("Invalid NPC object provided.")
        if not isinstance(scenario, Scenario):
            raise ValueError("Invalid scenario object provided.")
        if not isinstance(player_message, str):
            player_message = "[Player performed an action or said nothing]" if not player_message else player_message
        if not isinstance(victory_condition, dict):
            raise ValueError("Invalid victory condition provided.")

        # Gather current story state
        player_items_str = ", ".join(item.name for item in player.items) if player.items else "None"
        npc_items_str = ", ".join(item.name for item in npc.items) if npc.items else "None"
        
        # Describe victory condition for context
        vc_type = victory_condition.get("type")
        vc_item_name = victory_condition.get("item_name")
        vc_from_npc = victory_condition.get("from_npc", False)
        
        vc_description = "Unknown victory condition."
        if vc_type == "PLAYER_OBTAINS_ITEM":
            vc_description = f"The player must obtain '{vc_item_name}'"
            if vc_from_npc:
                vc_description += f" from the NPC"

        story_context = (
            f"Scenario: {scenario.name}\n"
            f"Scenario Description: {scenario.description}\n"
            f"Victory Condition: {vc_description}\n\n"
            f"Current Story State:\n"
            f"- Player ({player.name}) Items: [{player_items_str}]\n"
            f"- NPC ({npc.name}) Items: [{npc_items_str}]\n"
            f"- NPC Personality: {npc.personality}\n"
            f"- NPC Goal: {npc.goal}\n"
            f"- NPC Disposition: {npc.disposition}\n"
            f"- NPC Current Direction: {npc.direction if npc.direction else 'None'}"
        )

        interaction_summary = (
            f"Latest interaction:\n"
            f"{player.name} (Player): \"{player_message}\"\n"
            f"{npc.name} (NPC): \"{npc_response if npc_response else '[No verbal response]'}\""
        )

        system_prompt = (
            "You are a narrative Game Master AI. Your role is to provide subtle story direction to NPCs "
            "to help guide the narrative toward interesting developments and the scenario's victory condition. "
            "Analyze the current story state and latest interaction to determine if the NPC needs new narrative direction. "
            "Consider factors like: story progression, proximity to victory condition, character motivations, "
            "dramatic tension, and natural story flow. "
            "Direction should be subtle guidance that helps the NPC make choices that advance the story "
            "while staying true to their personality and goals. "
            "Examples of good direction: 'Consider being more forthcoming about your knowledge', "
            "'Show growing trust but maintain some caution', 'Hint at the importance of the item you possess', "
            "'Begin to reveal your true motivations', 'Express concern about the player's intentions'. "
            "Only provide direction if it would meaningfully advance the story or create interesting narrative moments. "
            "Avoid direction that would force specific actions or break character consistency. "
            "Respond ONLY with a JSON object with three keys: 'should_provide_direction' (boolean), "
            "'new_direction' (string, or empty if no direction needed), and 'reason' (string, or empty if no direction needed)."
        )

        user_prompt = (
            f"{story_context}\n\n"
            f"{interaction_summary}\n\n"
            "Based on the scenario, current story state, and latest interaction, should the NPC receive "
            "new narrative direction to help advance the story? Provide your response as a JSON object."
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

        try:
            response = litellm.completion(
                model="openai/gpt-4.1-mini",
                messages=messages,
                temperature=0.3, # Slightly creative but focused
                response_format={"type": "json_object"}
            )
            raw_response_content = response.choices[0].message.content
            
            if not raw_response_content:
                rprint(Text("GM Direction AI returned empty response. Assuming no direction needed.", style="dim yellow"))
                return False, "", ""

            parsed_json = json.loads(raw_response_content)

            should_provide_direction = parsed_json.get("should_provide_direction", False)
            new_direction = parsed_json.get("new_direction", "")
            reason = parsed_json.get("reason", "")

            if not isinstance(should_provide_direction, bool):
                rprint(Text(f"GM Direction AI: 'should_provide_direction' is not a boolean. Defaulting to False. JSON: {parsed_json}", style="red"))
                return False, "", ""
            
            if should_provide_direction and (not isinstance(new_direction, str) or not new_direction):
                rprint(Text(f"GM Direction AI: 'should_provide_direction' is True but 'new_direction' is invalid. Reverting to no direction. JSON: {parsed_json}", style="red"))
                return False, "", ""
            
            if should_provide_direction and (not isinstance(reason, str) or not reason):
                rprint(Text(f"GM Direction AI: 'should_provide_direction' is True but 'reason' is invalid. Using default reason. JSON: {parsed_json}", style="yellow"))
                reason = "GM determined new direction would help advance the story."

            return should_provide_direction, new_direction if should_provide_direction else "", reason if should_provide_direction else ""

        except json.JSONDecodeError as e:
            rprint(Text(f"[bold red]Error decoding JSON from GM Direction AI: {e}. Raw: '{raw_response_content}'. Defaulting to no direction.[/bold red]"))
            return False, "", ""
        except Exception as e:
            rprint(Text(f"[bold red]Error during GM Direction AI assessment: {e}. Defaulting to no direction.[/bold red]"))
            return False, "", "" 

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
                model="openai/gpt-4.1-mini",
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