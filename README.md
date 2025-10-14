# EduGPT-PersonalisedLearning  
**MSc Project: Designing and Delivering Personalised Learning Pathways using Role-Playing AI Agents**  

This project extends the [EduGPT](https://github.com/hqanhh/EduGPT) framework to design and evaluate an AI-powered personalised learning system. The aim is to create a multi-agent “AI Educator” that can:  
1. Generate a personalised syllabus from learner goals using role-playing agents.  
2. Deliver lessons through an instructor agent with **retrieval-augmented generation (RAG)** for grounded, source-based teaching.  
3. Provide **adaptive assessment** that adjusts difficulty and pacing based on learner performance.  
4. Maintain a learner model to track mastery and guide ongoing pathway adaptation.  



## ✨ Features (Planned Extensions Beyond EduGPT)  
- **Multi-Agent Syllabus Planner** – learner advocate + curriculum designer agents negotiate and output a structured syllabus.  
- **Retrieval-Augmented Teaching** – instructor agent delivers lessons using external resources (OERs, textbooks, notes) with citations.  
- **Adaptive Quizzing** – assessment items aligned with objectives, difficulty adjusted in real time.  
- **Learner Profile & Progress Tracking** – dynamic model of goals, performance, and mastery levels.  
- **Evaluation Protocol** – system assessed via expert syllabus review, pre/post tests, and learner satisfaction surveys.  

## System Architecture
The diagram below shows the overall workflow of the AI Educator system, from learner input through syllabus generation, lesson delivery with retrieval-augmented generation, adaptive assessment, and continuous feedback loops.  

![System Architecture](./assets/ext_diagram.png)

## 🚀 Getting Started  

### 1. Clone the repository  
```bash
git clone https://github.com/anasraza57/EduGPT-PersonalisedLearning.git
cd EduGPT-PersonalisedLearning
```

### 2. Set up a virtual environment
```bash
make venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure API keys
Create a `.env` file in the root directory and add:
```bash
OPENAI_API_KEY=your_key_here
```

### 4. Run the baseline demo
```bash
python src/run.py
```


## 📖 Background
- **EduGPT**: A LangChain-based project where a learner and instructor agent role-play to generate a syllabus and deliver lessons.

- **EduGPT-PersonalisedLearning**: This fork extends EduGPT with retrieval grounding, adaptive assessment, and learner modelling to deliver a more personalised learning experience.

## 🧪 Testing

### Run All Tests
```bash
python -m unittest discover tests/unit -v
```

### Test Coverage
- **Configuration & Validation**: `test_config.py`, `test_validation.py`
- **Learner Profile**: `test_learner_model.py`, `test_learner_profile_validation.py`
- **RAG Instructor**: `test_rag_instructor.py`
- **Assessment System**:
  - `test_assessment_generator.py` - Question generation and validation
  - `test_grading_agent.py` - LLM-based grading for open-ended responses
  - `test_quiz_session.py` - Adaptive quiz and points-weighted scoring
  - `test_assessment_schemas.py` - Schema validation for assessments and quiz sessions

### Run Specific Test Suites
```bash
# Learner profile tests
python -m unittest tests.unit.test_learner_model -v

# Assessment system tests
python -m unittest tests.unit.test_assessment_generator -v
python -m unittest tests.unit.test_grading_agent -v
python -m unittest tests.unit.test_quiz_session -v

# Schema validation tests
python -m unittest tests.unit.test_assessment_schemas -v
```
