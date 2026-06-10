import os
import re

tools_dir = 'app/agent/tools'

for filename in os.listdir(tools_dir):
    if not filename.endswith('.py'):
        continue
    filepath = os.path.join(tools_dir, filename)
    with open(filepath, 'r') as f:
        content = f.read()
    
    # In base.py
    if filename == 'base.py':
        content = content.replace("from anthropic import AsyncAnthropic", "from app.gemini.client import GeminiClient")
        content = content.replace("client: AsyncAnthropic", "client: GeminiClient")
        
        # Replace _extract_tool_use
        old_extract = '''    def _extract_tool_use(self, response: Any, tool_name: str) -> Optional[Dict[str, Any]]:
        """Parse Claude's tool_use response block."""
        for block in response.content:
            if block.type == "tool_use" and block.name == tool_name:
                return block.input
        return None'''
        new_extract = '''    def _parse_json_response(self, text: str) -> Optional[Dict[str, Any]]:
        import json
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        elif text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        try:
            return json.loads(text.strip())
        except json.JSONDecodeError:
            try:
                start = text.find('{')
                end = text.rfind('}') + 1
                return json.loads(text[start:end])
            except:
                return None'''
        content = content.replace(old_extract, new_extract)
        
        # Replace _count_tokens
        old_count = '''    def _count_tokens(self, response: Any) -> int:
        try:
            return response.usage.input_tokens + response.usage.output_tokens
        except Exception:
            return 0'''
        new_count = '''    def _count_tokens(self, text: str) -> int:
        return len(text) // 4  # Rough estimate for Gemini'''
        content = content.replace(old_count, new_count)
        
        with open(filepath, 'w') as f:
            f.write(content)
        continue
        
    # In other tool files
    
    # 1. Change self.client.messages.create
    # Regex to capture the try block and replace
    pattern = r'try:\s*response = await self\.client\.messages\.create\([\s\S]*?messages=\[\{"role": "user", "content": prompt\}\],\s*\)\s*except Exception as exc:\s*logger\.error\("[^"]+", error=str\(exc\)\)\s*return self\._empty_result\(task, f"Claude API error: \{exc\}"\)'
    
    # we need the tool name for raw variable assignment
    tool_name_match = re.search(r'self\._extract_tool_use\(response, "([^"]+)"\)', content)
    if not tool_name_match:
        print(f"Skipping {filename} - couldn't find extract_tool_use")
        continue
    
    tool_name = tool_name_match.group(1)
    
    # find system prompt var
    system_prompt_match = re.search(r'system=([^,]+),', content)
    sys_prompt = system_prompt_match.group(1) if system_prompt_match else "''"
    
    replacement = f'''try:
            import json
            prompt_with_schema = f"{{ {sys_prompt} }}\\n\\n{{prompt}}\\n\\nPlease output ONLY valid JSON matching the following schema:\\n{{json.dumps(_TOOL_SCHEMA['input_schema'])}}"
            response_text = await self.client.generate_content(
                prompt=prompt_with_schema,
                model_type="text",
            )
        except Exception as exc:
            logger.error(f"{{self.name}} API error", error=str(exc))
            return self._empty_result(task, f"Gemini API error: {{exc}}")'''
            
    new_content = re.sub(pattern, replacement, content)
    
    # 2. Change raw = self._extract_tool_use(...)
    new_content = new_content.replace(f'raw = self._extract_tool_use(response, "{tool_name}") or {{}}', 'raw = self._parse_json_response(response_text) or {}')
    
    # 3. Change tokens = self._count_tokens(response)
    new_content = new_content.replace('tokens = self._count_tokens(response)', 'tokens = self._count_tokens(response_text)')
    
    # 4. Change response.usage.input_tokens in state.add_tokens
    token_usage_pattern = r'state\.add_tokens\([\s\S]*?\)'
    new_content = re.sub(token_usage_pattern, 'state.add_tokens(len(prompt) // 4, tokens)', new_content)
    
    if new_content != content:
        with open(filepath, 'w') as f:
            f.write(new_content)
        print(f"Updated {filename}")
    else:
        print(f"No changes made to {filename}")

print("Done migration!")
