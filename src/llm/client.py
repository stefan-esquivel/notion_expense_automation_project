"""OpenAI client wrapper for receipt processing."""

import json
import os
from typing import Optional, Dict, Any
from openai import OpenAI

# Import config to ensure .env is loaded
from config import Config

from llm.prompts import (
    EXTRACT_RECEIPT_SYSTEM,
    EXTRACT_RECEIPT_USER,
    VALIDATE_RECEIPT_SYSTEM,
    VALIDATE_RECEIPT_USER,
    ENRICH_RECEIPT_SYSTEM,
    ENRICH_RECEIPT_USER,
    PARSE_DATE_SYSTEM,
    PARSE_DATE_USER,
    EXTRACT_ITEMS_SYSTEM,
    EXTRACT_ITEMS_USER,
)


class ReceiptLLMClient:
    """Client for LLM-based receipt processing operations."""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o-mini"):
        """
        Initialize the LLM client.
        
        Args:
            api_key: OpenAI API key (defaults to Config.OPENAI_API_KEY)
            model: Model to use (gpt-4o-mini is cost-effective for structured extraction)
        """
        self.api_key = api_key or Config.OPENAI_API_KEY
        if not self.api_key:
            raise ValueError("OpenAI API key not provided. Set OPENAI_API_KEY in .env file")
        
        self.client = OpenAI(api_key=self.api_key)
        self.model = model
    
    def _call_llm(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.1,
        response_format: Optional[Dict[str, str]] = None
    ) -> str:
        """
        Internal method to call OpenAI API.
        
        Args:
            system_prompt: System message
            user_prompt: User message
            temperature: Sampling temperature (lower = more deterministic)
            response_format: Optional response format (e.g., {"type": "json_object"})
        
        Returns:
            Response text from the model
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
        }
        
        # Add response format if specified (for JSON mode)
        if response_format:
            kwargs["response_format"] = response_format
        
        response = self.client.chat.completions.create(**kwargs)
        return response.choices[0].message.content
    
    def extract_receipt(self, raw_text: str) -> Dict[str, Any]:
        """
        Extract structured data from receipt text using LLM.
        
        Args:
            raw_text: Raw text extracted from PDF
        
        Returns:
            Dictionary with extracted receipt data
        """
        user_prompt = EXTRACT_RECEIPT_USER.format(raw_text=raw_text)
        
        response = self._call_llm(
            system_prompt=EXTRACT_RECEIPT_SYSTEM,
            user_prompt=user_prompt,
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        
        try:
            return json.loads(response)
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse LLM response as JSON: {e}\nResponse: {response}")
    
    def validate_receipt(
        self,
        raw_text: str,
        merchant: str,
        date: str,
        amount: float
    ) -> Dict[str, Any]:
        """
        Validate and correct extracted receipt data using LLM.
        
        Args:
            raw_text: Original receipt text
            merchant: Extracted merchant name
            date: Extracted date
            amount: Extracted amount
        
        Returns:
            Dictionary with validated/corrected data
        """
        user_prompt = VALIDATE_RECEIPT_USER.format(
            raw_text=raw_text,
            merchant=merchant,
            date=date,
            amount=amount
        )
        
        response = self._call_llm(
            system_prompt=VALIDATE_RECEIPT_SYSTEM,
            user_prompt=user_prompt,
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        
        try:
            return json.loads(response)
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse LLM response as JSON: {e}\nResponse: {response}")
    
    def enrich_receipt(
        self,
        merchant: str,
        date: str,
        items: Optional[list] = None
    ) -> Dict[str, Any]:
        """
        Enrich receipt with categorization using LLM.
        
        Args:
            merchant: Merchant name
            date: Transaction date
            items: List of items purchased (optional, helps with categorization)
        
        Returns:
            Dictionary with enrichment data (category, confidence, notes)
        """
        # Format items for prompt - convert Pydantic models to dicts if needed
        if items:
            # Check if items are Pydantic models and convert to dicts
            items_list = []
            for item in items:
                if hasattr(item, 'model_dump'):  # Pydantic v2
                    items_list.append(item.model_dump())
                elif hasattr(item, 'dict'):  # Pydantic v1
                    items_list.append(item.dict())
                else:
                    items_list.append(item)
            items_str = json.dumps(items_list)
        else:
            items_str = "[]"
        
        user_prompt = ENRICH_RECEIPT_USER.format(
            merchant=merchant,
            date=date,
            items=items_str
        )
        
        response = self._call_llm(
            system_prompt=ENRICH_RECEIPT_SYSTEM,
            user_prompt=user_prompt,
            temperature=0.2,  # Slightly higher for creative categorization
            response_format={"type": "json_object"}
        )
        
        try:
            return json.loads(response)
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse LLM response as JSON: {e}\nResponse: {response}")

    def parse_date(self, date_text: str, context: str = "") -> Dict[str, Any]:
        """
        Parse ambiguous date formats using LLM.
        
        Args:
            date_text: Date string to parse
            context: Surrounding text for context
        
        Returns:
            Dictionary with parsed date and confidence
        """
        user_prompt = PARSE_DATE_USER.format(
            date_text=date_text,
            context=context[:200]  # Limit context to 200 chars
        )
        
        response = self._call_llm(
            system_prompt=PARSE_DATE_SYSTEM,
            user_prompt=user_prompt,
            temperature=0.0,  # Very deterministic for date parsing
            response_format={"type": "json_object"}
        )
        
        try:
            return json.loads(response)
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse LLM response as JSON: {e}\nResponse: {response}")
    
    def extract_items(self, raw_text: str) -> Dict[str, Any]:
        """
        Extract individual line items from receipt text using LLM.
        
        Args:
            raw_text: Raw text extracted from PDF
        
        Returns:
            Dictionary with "items" array containing name, price, category for each item
        """
        user_prompt = EXTRACT_ITEMS_USER.format(raw_text=raw_text)
        
        response = self._call_llm(
            system_prompt=EXTRACT_ITEMS_SYSTEM,
            user_prompt=user_prompt,
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        
        try:
            return json.loads(response)
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse LLM response as JSON: {e}\nResponse: {response}")


def main():
    """Test the LLM client with a simple message."""
    print("\n" + "="*60)
    print("Testing OpenAI LLM Client")
    print("="*60 + "\n")
    
    try:
        # Initialize client
        print("Initializing client...")
        client = ReceiptLLMClient()
        
        # Simple test
        print("Sending test message to LLM...\n")
        
        response = client._call_llm(
            system_prompt="You are a helpful assistant.",
            user_prompt="Say hi and tell me you're working!",
            temperature=0.7
        )
        
        print("LLM Response:")
        print("-" * 60)
        print(response)
        print("-" * 60)
        print("\n✅ LLM client is working!\n")
        
    except Exception as e:
        print(f"\n❌ Error: {e}\n")
        print("Make sure you have:")
        print("1. Installed openai: pip install openai")
        print("2. Set OPENAI_API_KEY environment variable")
        print("   export OPENAI_API_KEY='sk-...'")


if __name__ == "__main__":
    main()
    