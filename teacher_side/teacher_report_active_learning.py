import os
import time
from typing import Dict, Any

import yaml

from teacher_side.teacher_prompts import extract_teacher_report_results
from teacher_side.teacher_report import TeacherReport
from utils.utils import get_logger


def task_student_interaction(lan="English", format='JSON'):
    """Analyze the extent to which students interact during the lecture."""
    prompt = (
        "Task name: <name>student_interaction</name>\n"
        """Analyze the lecture transcript and assess the level of student interaction. Specifically:

1. **Discussion Opportunities** - Identify moments where students engage in discussion:
   - Find explicit discussion prompts or periods
   - Note any student-to-student dialogue
   - Rate the frequency and quality of discussions

2. **Polls & Interactive Questions** - Document all interactive questioning:
   - List all poll questions or voting opportunities
   - Count how many times the instructor asks for a show of hands
   - Identify clicker questions or digital polling

3. **Student Questions** - Track when students ask questions:
   - Count student-initiated questions
   - Note how the instructor responds (encourages/dismisses)
   - Identify if questions lead to extended discussion

4. **Problem-Solving Activities** - Find instances where students actively solve problems:
   - Individual problem-solving exercises
   - Real-time calculations or applications
   - Case studies or scenarios students work through

5. **Interaction Quality** - Assess the depth of interaction:
   - Surface-level (yes/no answers) vs. deep engagement
   - Evidence of peer learning
   - Student contributions that advance the lesson"""
        "\ninclude the following: strengths, weaknesses, recommendations, evidence"
        f"\nThe format of the output should be {format}."
        f"\n<output_language>{lan}</output_language>"
    )
    return prompt


def task_short_tasks(lan="English", format='JSON'):
    """Evaluate how often the instructor includes brief active learning tasks."""
    prompt = (
        "Task name: <name>short_tasks</name>\n"
        """Evaluate the frequency and effectiveness of short active learning tasks:

1. **Think-Pair-Share** - Identify think-pair-share sequences:
   - Quote the prompts for thinking individually
   - Note when students are asked to pair up
   - Document sharing moments with the class
   - Rate how well the instructor structures each phase

2. **Mini-Exercises** - Find all brief exercises or activities:
   - Quick calculations or estimations
   - Short writing prompts
   - Minute papers or quick reflections
   - Drawing/diagramming tasks
   - List duration of each task (if mentioned)

3. **Turn-and-Talk** - Identify informal peer discussion prompts:
   - "Turn to your neighbor and discuss..."
   - "Take 30 seconds to explain to a partner..."
   - Rate how clearly instructions are given

4. **Active Demonstrations** - Note when students actively demonstrate:
   - Physical demonstrations or role-play
   - Show-of-hands for different answers
   - Student volunteers showing work

5. **Task Frequency & Spacing** - Analyze the distribution:
   - Map when tasks occur throughout the lecture
   - Identify long stretches without active tasks
   - Assess if tasks break up lecture effectively"""
        "\ninclude the following: strengths, weaknesses, recommendations, evidence"
        f"\nThe format of the output should be {format}."
        f"\n<output_language>{lan}</output_language>"
    )
    return prompt


def task_student_reflection(lan="English", format='JSON'):
    """Assess evidence of student reflection and metacognition."""
    prompt = (
        "Task name: <name>student_reflection</name>\n"
        """Assess how the instructor promotes student reflection and checking understanding:

1. **Self-Assessment Prompts** - Find moments where students check their own understanding:
   - "Do you understand this?" or "Does this make sense?"
   - "Rate your confidence on this concept"
   - "What questions do you still have?"
   - Self-quizzes or practice problems for self-checking

2. **Metacognitive Prompts** - Identify reflection on learning process:
   - "How did you arrive at that answer?"
   - "What strategy did you use?"
   - "Why was this difficult?"
   - "What would you do differently next time?"

3. **Confusion Checks** - Document when instructor checks for confusion:
   - "What's still unclear?"
   - "What's the muddiest point?"
   - Exit tickets or quick assessments
   - Show of thumbs (up/middle/down) for understanding

4. **Reflection Activities** - List explicit reflection tasks:
   - One-minute papers
   - Learning journals or logs
   - "What surprised you?" prompts
   - Connections to prior knowledge

5. **Wait Time for Thinking** - Assess if instructor provides thinking time:
   - Note if questions are followed by silence/wait time
   - Evidence of "think time" before answering
   - "Take a moment to think..." instructions"""
        "\ninclude the following: strengths, weaknesses, recommendations, evidence"
        f"\nThe format of the output should be {format}."
        f"\n<output_language>{lan}</output_language>"
    )
    return prompt


def task_collaboration(lan="English", format='JSON'):
    """Evaluate the use of collaborative learning activities."""
    prompt = (
        "Task name: <name>collaboration</name>\n"
        """Evaluate how the instructor incorporates collaboration and group work:

1. **Group Work Structures** - Identify all collaborative activities:
   - Formal group assignments or projects
   - Small group discussions (specify group size if mentioned)
   - Peer teaching moments
   - Team problem-solving
   - List the duration and purpose of each

2. **Breakout Tasks** - Document breakout room or separate group activities:
   - What task were groups assigned?
   - How long were breakouts?
   - How were groups formed? (random/strategic/self-selected)
   - Were roles assigned? (facilitator, recorder, presenter)

3. **Peer Learning** - Find instances of students teaching each other:
   - "Explain this to your partner"
   - Students presenting to class
   - Peer feedback or peer review
   - Jigsaw activities where students become "experts"

4. **Collaborative Accountability** - Assess how instructor structures collaboration:
   - Are there clear expectations for participation?
   - Evidence of individual accountability within groups
   - Reporting out or sharing group insights
   - Equal participation encouraged?

5. **Social Construction of Knowledge** - Identify if learning is co-constructed:
   - Building on each other's ideas
   - Class-wide brainstorming
   - Consensus-building activities
   - Collective problem-solving"""
        "\ninclude the following: strengths, weaknesses, recommendations, evidence"
        f"\nThe format of the output should be {format}."
        f"\n<output_language>{lan}</output_language>"
    )
    return prompt


def task_student_choice(lan="English", format='JSON'):
    """Analyze opportunities for student choice and agency."""
    prompt = (
        "Task name: <name>student_choice</name>\n"
        """Analyze opportunities for student choice, autonomy, and agency:

1. **Choice in Activities** - Identify when students have options:
   - "Choose which problem to work on"
   - Multiple pathways to demonstrate learning
   - Option to work individually or in groups
   - Choice of topics or examples

2. **Autonomy in Process** - Find moments of student control:
   - Students deciding how to approach a problem
   - Freedom to use preferred methods or tools
   - Self-paced activities
   - Students directing the inquiry

3. **Voice in Content** - Assess if students influence what's covered:
   - "What would you like to explore further?"
   - Student questions shaping the discussion
   - Voting on topics or examples to cover
   - Student-generated examples or problems

4. **Self-Direction** - Document opportunities for independent work:
   - Open-ended problems with multiple solutions
   - Research or exploration time
   - Student choice in how to represent learning
   - Freedom to pursue tangential interests

5. **Agency Indicators** - Find evidence that students feel ownership:
   - Students making decisions about their learning
   - Negotiation of deadlines or requirements
   - Students proposing alternative approaches
   - Personalization of assignments"""
        "\ninclude the following: strengths, weaknesses, recommendations, evidence"
        f"\nThe format of the output should be {format}."
        f"\n<output_language>{lan}</output_language>"
    )
    return prompt


def task_learning_scaffolding(lan="English", format='JSON'):
    """Assess cognitive support and scaffolding for learning."""
    prompt = (
        "Task name: <name>learning_scaffolding</name>\n"
        """Assess the cognitive support and scaffolding provided to students:

1. **Chunking Complex Ideas** - Identify how instructor breaks down complexity:
   - Large concepts divided into smaller pieces
   - Step-by-step progression through difficult material
   - "Let's break this down..." moments
   - Use of sub-headings or clear segments
   - Rate the effectiveness of chunking

2. **Clear Transitions** - Document transitions between topics:
   - Signposting: "First... Next... Finally..."
   - "Now that we understand X, we can tackle Y"
   - Summaries before moving on
   - Preview of what's coming next
   - Explicit connections between sections

3. **Examples → Abstraction → Application** - Map the learning sequence:
   - Does instruction start with concrete examples?
   - When are abstract principles introduced?
   - Are there opportunities to apply concepts?
   - Identify the sequence: concrete-to-abstract or abstract-to-concrete
   - Rate the effectiveness of the progression

4. **Differentiated Support** - Find evidence of support for different learners:
   - Multiple representations (visual, verbal, symbolic)
   - Simpler explanations followed by more complex ones
   - Optional advanced content for those ahead
   - Additional support for struggling students
   - "If you're feeling lost, think of it this way..."

5. **Temporary Supports** - Identify scaffolds that can be removed:
   - Worked examples that gradually release responsibility
   - Templates or frameworks that guide initial work
   - Guided practice before independent practice
   - Hints or prompts that fade over time
   - Training wheels that get removed"""
        "\ninclude the following: strengths, weaknesses, recommendations, evidence"
        f"\nThe format of the output should be {format}."
        f"\n<output_language>{lan}</output_language>"
    )
    return prompt


tasks_dict = {
    "student_interaction": task_student_interaction,
    "short_tasks": task_short_tasks,
    "student_reflection": task_student_reflection,
    "collaboration": task_collaboration,
    "student_choice": task_student_choice,
    "learning_scaffolding": task_learning_scaffolding
}


def build_tasks_array(lan="English"):
    """Build a unified string of all active learning analysis tasks."""
    unified_tasks = ""
    for task in tasks_dict.values():
        unified_tasks += task(lan=lan) + "\n\n"
    return unified_tasks


class TeacherReportActiveLearning(TeacherReport):
    """Active learning analysis using Anthropic's Claude (default)."""
    def __init__(self, config: Dict[str, Any], api_key: str = None):
        super().__init__(config, api_key)

    def compose_system_prompt(self, lan="English"):
        """System prompt - defines the analyzer's role and output format."""
        system_prompt = (
            "You are an expert educational content analyzer specializing in active learning pedagogies. "
            "Your role is to analyze lecture transcriptions and assess the instructor's use of active learning techniques "
            "that promote student engagement, reflection, collaboration, and agency.\n\n"

            "You have deep knowledge of:\n"
            "1. **Active learning theory** (Bonwell & Eison, Freeman et al., Prince)\n"
            "2. **Cognitive science** of learning (retrieval practice, elaboration, metacognition)\n"
            "3. **Collaborative learning** (Johnson & Johnson, cooperative learning structures)\n"
            "4. **Student agency** and self-directed learning principles\n"
            "5. **Instructional scaffolding** (Vygotsky's ZPD, gradual release of responsibility)\n"
            "6. **Assessment for learning** (formative assessment, feedback loops)\n\n"

            "You must analyze across several dimensions and return valid JSON only (no markdown, no extra text).\n"
            "For each dimension, return this exact JSON structure:\n"
            "{\n"
            '  "dimension": "dimension_name",\n'
            '  "strengths": ["strength 1", "strength 2"],\n'
            '  "weaknesses": ["weakness 1", "weakness 2"],\n'
            '  "recommendations": ["recommendation 1", "recommendation 2"],\n'
            '  "evidence": ["quote 1", "quote 2"]\n'
            "}\n\n"

            "Return a JSON array containing all dimension analyses.\n\n"

            f"Here is the information about the course:\n"
            f"<transcript>{self.transcript}</transcript>\n\n"

            f"Output specifications:\n"
            f"<output_language>{lan}</output_language>\n"
            f"<course_name>{self.course_name}</course_name>\n"
            f"<class_level>{self.class_level}</class_level>"
        )

        self.system_prompt = system_prompt

    def compose_user_prompt(self, lan="English"):
        """User prompt - contains all the specific analysis tasks."""
        self.user_prompt = build_tasks_array(lan=lan)


class TeacherReportActiveLearningOR(TeacherReport):
    """Active learning analysis using OpenRouter (secondary option)."""
    def __init__(self, config: Dict[str, Any], api_key: str = None, base_url: str = "https://openrouter.ai/api/v1"):
        # Import the OR version
        from teacher_side.teacher_report import TeacherReportOR
        # Initialize with OpenRouter parent
        TeacherReportOR.__init__(self, config, api_key, base_url)

    # Share the same methods with TeacherReportActiveLearning
    compose_system_prompt = TeacherReportActiveLearning.compose_system_prompt
    compose_user_prompt = TeacherReportActiveLearning.compose_user_prompt


if __name__ == '__main__':
    # Configuration
    config_path = "./config.yaml"
    config = yaml.safe_load(open(config_path))
    logger = get_logger(__name__, config)

    # Get language from config, default to English if not specified
    language = config.get("language", "English")

    # Process video
    t0 = time.time()
    llmproxy = TeacherReportActiveLearning(config)
    llmproxy.course_name = config.get("course_name", "Unknown Course")
    llmproxy.class_level = config.get("class_level", "Unknown Level")

    llmproxy.prepare_content(lan=language)
    output = llmproxy.call_api()
    output_file = os.path.join(config["videos_dir"], "active_learning.txt")
    with open(output_file, "w") as file:
        file.write(output)
    print(output)

    logger.info(f'Pipeline completed in {time.time() - t0:.3f}s')