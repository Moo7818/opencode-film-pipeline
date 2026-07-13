# MCP Server Evaluation Guide

## Overview

This document provides guidance on creating comprehensive evaluations for MCP servers. Evaluations test whether LLMs can effectively use your MCP server to answer realistic, complex questions using only the tools provided.

---

## Quick Reference

### Evaluation Requirements
- Create 10 human-readable questions
- Questions must be READ-ONLY, INDEPENDENT, NON-DESTRUCTIVE
- Each question requires multiple tool calls (potentially dozens)
- Answers must be single, verifiable values
- Answers must be STABLE (won't change over time)

### Output Format
```xml
<evaluation>
   <qa_pair>
      <question>Your question here</question>
      <answer>Single verifiable answer</answer>
   </qa_pair>
</evaluation>
```

---

## Purpose of Evaluations

The measure of quality of an MCP server is NOT how well or comprehensively the server implements tools, but how well these implementations (input/output schemas, docstrings/descriptions, functionality) enable LLMs with no other context and access ONLY to the MCP servers to answer realistic and difficult questions.

## Evaluation Overview

Create 10 human-readable questions requiring ONLY READ-ONLY, INDEPENDENT, NON-DESTRUCTIVE, and IDEMPOTENT operations to answer. Each question should be:
- Realistic
- Clear and concise
- Unambiguous
- Complex, requiring potentially dozens of tool calls or steps
- Answerable with a single, verifiable value that you identify in advance

## Question Guidelines

### Core Requirements

1. **Questions MUST be independent**
   - Each question should NOT depend on the answer to any other question
   - Should not assume prior write operations from processing another question

2. **Questions MUST require ONLY NON-DESTRUCTIVE AND IDEMPOTENT tool use**
   - Should not instruct or require modifying state to arrive at the correct answer

3. **Questions must be REALISTIC, CLEAR, CONCISE, and COMPLEX**
   - Must require another LLM to use multiple (potentially dozens of) tools or steps to answer

### Complexity and Depth

4. **Questions must require deep exploration**
   - Consider multi-hop questions requiring multiple sub-questions and sequential tool calls
   - Each step should benefit from information found in previous questions

5. **Questions may require extensive paging**
   - May need paging through multiple pages of results
   - May require querying old data (1-2 years out-of-date) to find niche information
   - The questions must be DIFFICULT

6. **Questions must require deep understanding**
   - Rather than surface-level knowledge
   - May pose complex ideas as True/False questions requiring evidence
   - May use multiple-choice format where LLM must search different hypotheses

7. **Questions must not be solvable with straightforward keyword search**
   - Do not include specific keywords from the target content
   - Use synonyms, related concepts, or paraphrases
   - Require multiple searches, analyzing multiple related items, extracting context, then deriving the answer

### Tool Testing

8. **Questions should stress-test tool return values**
   - May elicit tools returning large JSON objects or lists, overwhelming the LLM
   - Should require understanding multiple modalities of data
   - Should probe the tool's ability to return all useful forms of data

9. **Questions should MOSTLY reflect real human use cases**
   - The kinds of information retrieval tasks that HUMANS assisted by an LLM would care about

10. **Questions may require dozens of tool calls**
    - This challenges LLMs with limited context
    - Encourages MCP server tools to reduce information returned

11. **Include ambiguous questions**
    - May be ambiguous OR require difficult decisions on which tools to call
    - Force the LLM to potentially make mistakes or misinterpret
    - Ensure that despite AMBIGUITY, there is STILL A SINGLE VERIFIABLE ANSWER

### Stability

12. **Questions must be designed so the answer DOES NOT CHANGE**
    - Do not ask questions that rely on "current state" which is dynamic

13. **DO NOT let the MCP server RESTRICT the kinds of questions you create**
    - Create challenging and complex questions
    - Some may not be solvable with the available MCP server tools

## Answer Guidelines

### Verification

1. **Answers must be VERIFIABLE via direct string comparison**
   - If the answer can be re-written in many formats, clearly specify the output format in the QUESTION
   - Answer should be a single VERIFIABLE value such as:
     - User ID, user name, display name
     - Channel ID, channel name
     - Message ID, string
     - URL, title
     - Numerical quantity
     - Timestamp, datetime
     - Boolean (for True/False questions)
     - Email address, phone number
     - File ID, file name, file extension
     - Multiple choice answer
   - Answer will be verified using DIRECT STRING COMPARISON

### Readability

2. **Answers should generally prefer HUMAN-READABLE formats**
   - Rather than opaque IDs (though IDs are acceptable)

### Stability

3. **Answers must be STABLE/STATIONARY**
   - Look at old content (e.g., conversations that have ended, projects that have launched)
   - Create QUESTIONS based on "closed" concepts that will always return the same answer
   - Rely on context UNLIKELY to change

4. **Answers must be CLEAR and UNAMBIGUOUS**
   - Questions must be designed so there is a single, clear answer

### Diversity

5. **Answers must be DIVERSE**
   - Answer should be a single VERIFIABLE value in diverse modalities and formats

6. **Answers must NOT be complex structures**
   - Not a list of values, complex object, or list of IDs
   - UNLESS the answer can be straightforwardly verified using DIRECT STRING COMPARISON

## Evaluation Process

### Step 1: Documentation Inspection

Read the documentation of the target API to understand:
- Available endpoints and functionality
- Parallelize this step AS MUCH AS POSSIBLE

### Step 2: Tool Inspection

List the tools available in the MCP server:
- Inspect the MCP server directly
- Understand input/output schemas, docstrings, and descriptions
- WITHOUT calling the tools themselves at this stage

### Step 3: Developing Understanding

Repeat steps 1 & 2 until you have a good understanding:
- Iterate multiple times
- At NO stage should you READ the code of the MCP server implementation itself

### Step 4: Read-Only Content Inspection

After understanding the API and tools, USE the MCP server tools:
- Inspect content using READ-ONLY and NON-DESTRUCTIVE operations ONLY
- Should NOT call any tools that modify state
- Parallelize this step with individual sub-agents
- BE CAREFUL: SOME TOOLS may return LOTS OF DATA
- Make INCREMENTAL, SMALL, AND TARGETED tool calls

### Step 5: Task Generation

After inspecting the content, create 10 human-readable questions.

## Output Format

```xml
<evaluation>
   <qa_pair>
      <question>Your question here</question>
      <answer>Your answer here</answer>
   </qa_pair>
</evaluation>
```

## Evaluation Examples

### Good Questions

```xml
<qa_pair>
   <question>Find the repository that was archived in Q3 2023 and had previously been the most forked project in the organization. What was the primary programming language used in that repository?</question>
   <answer>Python</answer>
</qa_pair>
```

```xml
<qa_pair>
   <question>Among all bugs reported in January 2024 that were marked as critical priority, which assignee resolved the highest percentage of their assigned bugs within 48 hours? Provide the assignee's username.</question>
   <answer>alex_eng</answer>
</qa_pair>
```

### Poor Questions

```xml
<qa_pair>
   <question>How many open issues are currently assigned to the engineering team?</question>
   <answer>47</answer>
</qa_pair>
```
This is poor because the answer changes over time.

```xml
<qa_pair>
   <question>Find the pull request with title "Add authentication feature" and tell me who created it.</question>
   <answer>developer123</answer>
</qa_pair>
```
This is poor because it can be solved with a straightforward keyword search.

## Verification Process

After creating evaluations:

1. **Examine the XML file** to understand the schema
2. **Load each task instruction** and in parallel using the MCP server and tools, identify the correct answer
3. **Flag any operations** that require WRITE or DESTRUCTIVE operations
4. **Accumulate all CORRECT answers** and replace any incorrect answers
5. **Remove any `<qa_pair>`** that require WRITE or DESTRUCTIVE operations

## Tips for Creating Quality Evaluations

1. **Think Hard and Plan Ahead** before generating tasks
2. **Parallelize Where Opportunity Arises**
3. **Focus on Realistic Use Cases**
4. **Create Challenging Questions**
5. **Ensure Stability** by using historical data
6. **Verify Answers** by solving the questions yourself
7. **Iterate and Refine**

---

# Running Evaluations

## Setup

```bash
pip install anthropic mcp
export ANTHROPIC_API_KEY=your_api_key_here
```

## Command-Line Options

```
usage: evaluation.py [-h] [-t {stdio,sse,http}] [-m MODEL] [-c COMMAND]
                     [-a ARGS [ARGS ...]] [-e ENV [ENV ...]] [-u URL]
                     [-H HEADERS [HEADERS ...]] [-o OUTPUT]
                     eval_file

positional arguments:
  eval_file             Path to evaluation XML file

optional arguments:
  -h, --help            Show help message
  -t, --transport       Transport type: stdio, sse, or http (default: stdio)
  -m, --model           Claude model to use
  -o, --output          Output file for report

stdio options:
  -c, --command         Command to run MCP server
  -a, --args            Arguments for the command
  -e, --env             Environment variables in KEY=VALUE format

sse/http options:
  -u, --url             MCP server URL
  -H, --header          HTTP headers in 'Key: Value' format
```

## Examples

### Local STDIO Server

```bash
python scripts/evaluation.py -t stdio -c python -a my_mcp_server.py evaluation.xml
```

### SSE Server

```bash
python scripts/evaluation.py -t sse -u https://example.com/mcp evaluation.xml
```

### HTTP Server

```bash
python scripts/evaluation.py -t http -u https://example.com/mcp evaluation.xml
```
