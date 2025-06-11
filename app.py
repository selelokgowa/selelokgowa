from flask import Flask, request, jsonify
from datetime import datetime
import difflib
import re
import json
import os
import spacy
from spellchecker import SpellChecker
from collections import Counter
import string
from flask_cors import CORS # <--- ADDED THIS IMPORT

# Load spaCy model (install with: python -m spacy download en_core_web_sm)
try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    print("Please install spaCy English model: python -m spacy download en_core_web_sm")
    nlp = None

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_super_secret_key_here' # It's good practice to set a secret key for Flask apps, especially if using sessions
CORS(app) # <--- ADDED THIS LINE TO ENABLE CORS FOR ALL ROUTES

class HomeAffairsChatbot:
    def __init__(self):
        # Initialize spell checker
        self.spell_checker = SpellChecker()

        # Add domain-specific words to spell checker
        domain_words = {
            'homeaffairs', 'ehomeaffairs', 'dha', 'smartcard', 'unabridged',
            'naturalization', 'biometrics', 'affidavit', 'impediment',
            'consulate', 'embassy', 'gauteng', 'kwazulu', 'natal', 'limpopo',
            'mpumalanga', 'noordwest', 'freestate', 'eastercape', 'westerncape',
            'northerncape', 'pretoria', 'johannesburg', 'capetown', 'durban'
        }
        self.spell_checker.word_frequency.load_words(domain_words)

        # Intent patterns for better classification
        self.intent_patterns = {
            'id_application': [
                'apply', 'application', 'get', 'obtain', 'new', 'smart card',
                'identity document', 'id book', 'green book'
            ],
            'passport_services': [
                'passport', 'travel document', 'renewal', 'renew', 'dha-73',
                'international travel', 'emergency passport'
            ],
            'birth_certificate': [
                'birth certificate', 'birth registration', 'unabridged',
                'born', 'baby', 'newborn', 'late registration'
            ],
            'death_certificate': [
                'death certificate', 'death registration', 'deceased',
                'died', 'funeral', 'burial'
            ],
            'marriage_services': [
                'marriage', 'wedding', 'married', 'spouse', 'marriage certificate',
                'marriage registration', 'civil union'
            ],
            'visa_immigration': [
                'visa', 'immigration', 'permit', 'foreign', 'visitor',
                'work permit', 'study permit', 'business visa'
            ],
            'citizenship': [
                'citizenship', 'citizen', 'naturalization', 'permanent residence',
                'pr', 'dual citizenship', 'retention'
            ],
            'lost_documents': [
                'lost', 'stolen', 'missing', 'replacement', 'affidavit',
                'police report'
            ],
            'appointments': [
                'appointment', 'booking', 'schedule', 'book', 'queue',
                'waiting time'
            ],
            'contact_info': [
                'contact', 'phone', 'call', 'address', 'location',
                'hotline', 'office hours'
            ]
        }
        self.qa_database = {
            # General Information
            "What is the South African Department of Home Affairs?":
                "The Department of Home Affairs manages civic services, including ID documents, passports, birth certificates, and immigration services.",
            "Where is the Department of Home Affairs headquarters?":
                "The headquarters is located in Pretoria, South Africa.",
            "How can I contact the Department of Home Affairs?":
                "You can call the national hotline at 0800 60 11 90 or visit their official website.",

            # ID Documents
            "How can I apply for a South African ID?":
                "Visit a Home Affairs office with your birth certificate and supporting documents. You'll need proof of citizenship and residence.",
            "what is ID?":
                "A South African ID is an Identity Document issued by the Department of Home Affairs to South African citizens and permanent residents. It serves as official proof of identity and is required for various activities such as voting, opening a bank account, employment, and accessing government services.",
            "How long does it take to get a South African ID?":
                "Processing time is typically 10-14 working days but may vary depending on demand and completeness of documentation.",
            "What is a smart ID card?":
                "A smart ID card is a secure replacement for the traditional green barcoded ID book. It contains biometric data and enhanced security features.",
            "Can I apply for a South African ID online?":
                "Yes, you can start the application online via eHomeAffairs but must visit an office for biometrics and document verification.",

            # Passports
            "What is a South African passport?":
                "A South African passport is an official travel document issued to citizens for international travel.",
            "How do I apply for a South African passport?":
                "Apply at Home Affairs with your ID, passport photos (50mm x 35mm), completed DHA-73 form, and payment of R400.",
            "How long does it take to get a South African passport?":
                "Standard processing takes 10-15 working days. Emergency processing is available for urgent travel needs.",
            "Can I track my passport application status?":
                "Yes, you can track your application online via the Department of Home Affairs website using your reference number.",

            # Birth Certificates
            "How do I apply for a birth certificate in South Africa?":
                "Apply at Home Affairs with proof of birth from a hospital, parents' IDs, and witness statements if required.",
            "How long does it take to get a birth certificate?":
                "Usually within 3-5 working days for normal registration. Late registration may take 2-4 weeks.",
            "Can I get a copy of my birth certificate?":
                "Yes, you can request a certified copy at Home Affairs offices for a prescribed fee.",

            # Death Certificates
            "How do I obtain a death certificate in South Africa?":
                "Apply at Home Affairs with a medical certificate of death, the deceased's ID, and proof of relationship.",
            "How long does it take to receive a death certificate?":
                "Usually within 3-5 working days after submission of complete documentation.",

            # Marriage & Divorce
            "How do I register a marriage in South Africa?":
                "Visit Home Affairs within 3 months of the ceremony with marriage certificate, IDs of both parties, and two witnesses.",
            "Can foreigners get married in South Africa?":
                "Yes, but additional documents like a Letter of No Impediment from their home country may be required.",
            "How do I apply for a marriage certificate?":
                "Apply at Home Affairs after the wedding with proof of marriage ceremony and required documentation.",

            # Immigration & Visas
            "How can I apply for a visa in South Africa?":
                "Submit visa applications at a South African embassy or consulate with required documents including proof of funds, return tickets, and accommodation.",
            "How long does it take to process a South African visa?":
                "Processing times vary by visa type but generally take 5-15 working days for tourist visas.",
            "Can I extend my South African visa?":
                "Yes, apply for an extension at the Department of Home Affairs at least 60 days before expiry.",
            "What are the types of South African visas available?":
                "Tourist visa, work visa, business visa, student visa, critical skills visa, spouse visa, and refugee permits.",

            # Lost or Stolen Documents
            "How do I report a lost or stolen ID or passport?":
                "Report it to the police immediately, obtain an affidavit, then apply for a replacement at Home Affairs with supporting documents.",
            "What should I do if I lose my birth certificate?":
                "Apply for a replacement at Home Affairs with your current ID and an affidavit explaining the loss.",

            # Citizenship & Permanent Residence
            "How do I apply for South African citizenship?":
                "Apply at Home Affairs if you qualify through birth, descent, or naturalization. Requirements include residency period and language proficiency.",
            "How can I get permanent residence in South Africa?":
                "Apply through Home Affairs with proof of eligibility such as work permit, marriage to SA citizen, or refugee status.",

            # Working Hours & Online Services
            "What are the working hours at Home Affairs?":
                "Home Affairs offices are usually open Monday to Friday from 8:00 AM to 3:30 PM. Some branches offer Saturday services from 8:00 AM to 1:00 PM.",
            "Can I apply for Home Affairs services online?":
                "Yes, some services like smart ID and passport applications can be started online via eHomeAffairs portal.",

            # Additional Services
            "How do I book an appointment at Home Affairs?":
                "Book an appointment through the eHomeAffairs website, call 0800 60 11 90, or visit an office directly.",
            "How do I check my application status with Home Affairs?":
                "Check your status online via the Department of Home Affairs website using your reference number or visit a local office.",
            "Can I apply for dual citizenship in South Africa?":
                "Yes, but you must apply for retention of SA citizenship before obtaining another nationality.",
            "How do I obtain an unabridged birth certificate?":
                "Apply at Home Affairs with proof of identity. Unabridged certificates show parents' details and are required for certain legal processes.",
        }

        # Keywords for better matching
        self.keywords = {
            'id': ['id', 'identity', 'document', 'smart card'],
            'passport': ['passport', 'travel', 'international'],
            'birth': ['birth', 'certificate', 'born', 'baby'],
            'death': ['death', 'deceased', 'died'],
            'marriage': ['marriage', 'married', 'wedding', 'spouse'],
            'visa': ['visa', 'immigration', 'foreign', 'permit'],
            'citizenship': ['citizenship', 'citizen', 'naturalization'],
            'appointment': ['appointment', 'booking', 'schedule'],
            'lost': ['lost', 'stolen', 'missing'],
            'online': ['online', 'internet', 'website'],
            'hours': ['hours', 'time', 'open', 'working'],
            'contact': ['contact', 'phone', 'call', 'hotline']
        }

        self.chat_history = []
        self.stats = {
            'messages_processed': 247,
            'satisfaction_rate': 96,
            'popular_services': {
                'Passport Services': 34,
                'ID Applications': 28,
                'Birth Certificates': 22,
                'Marriage Registration': 16
            }
        }

    def correct_spelling(self, text):
        """Correct spelling mistakes in user input"""
        words = text.split()
        corrected_words = []
        individual_corrections = []

        for word in words:
            # Remove punctuation for spell checking
            clean_word = word.strip(string.punctuation).lower()

            # Skip if word is too short or is a number
            if len(clean_word) < 2 or clean_word.isdigit():
                corrected_words.append(word)
                continue

            # Check if word is misspelled
            if clean_word not in self.spell_checker:
                # Get correction suggestions
                suggestions = self.spell_checker.candidates(clean_word)
                if suggestions:
                    # Use the most likely correction
                    correction = min(suggestions, key=lambda x: self.spell_checker.word_frequency[x])
                    # Preserve original capitalization
                    if word and word[0].isupper():
                        correction = correction.capitalize()
                    corrected_words.append(correction)
                    if correction.lower() != clean_word:
                        individual_corrections.append({
                            'original': word,
                            'corrected': correction
                        })
                else:
                    corrected_words.append(word)
            else:
                corrected_words.append(word)

        return ' '.join(corrected_words), individual_corrections

    def extract_entities(self, text):
        """Extract named entities using spaCy"""
        if not nlp:
            return []

        doc = nlp(text)
        entities = []

        for ent in doc.ents:
            entities.append({
                'text': ent.text,
                'label': ent.label_,
                'description': spacy.explain(ent.label_)
            })

        return entities

    def classify_intent(self, text):
        """Classify user intent using pattern matching and NLP"""
        text_lower = text.lower()
        intent_scores = {}

        # Calculate scores for each intent
        for intent, patterns in self.intent_patterns.items():
            score = 0
            for pattern in patterns:
                if pattern in text_lower:
                    # Give higher score for exact matches
                    score += 2 if pattern == text_lower else 1

            # Normalize score by number of patterns
            intent_scores[intent] = score / len(patterns) if patterns else 0

        # Return the intent with highest score
        if intent_scores:
            best_intent = max(intent_scores, key=intent_scores.get)
            if intent_scores[best_intent] > 0:
                return best_intent

        return 'general'

    def extract_keywords_nlp(self, text):
        """Extract keywords using spaCy NLP"""
        if not nlp:
            return self.extract_keywords(text)  # Fallback to basic method

        doc = nlp(text)
        keywords = []

        # Extract important tokens (nouns, adjectives, proper nouns)
        for token in doc:
            if (token.pos_ in ['NOUN', 'PROPN', 'ADJ'] and
                not token.is_stop and
                not token.is_punct and
                len(token.text) > 2):
                keywords.append(token.lemma_.lower())

        # Also extract named entities
        for ent in doc.ents:
            if ent.label_ in ['ORG', 'GPE', 'PERSON']:
                keywords.append(ent.text.lower())

        return list(set(keywords))  # Remove duplicates

    def semantic_similarity(self, text1, text2):
        """Calculate semantic similarity using spaCy word vectors"""
        if not nlp or not nlp.vocab.has_vector('test'): # Check if vectors are loaded (dummy check)
            return self.calculate_similarity(text1, text2)  # Fallback

        doc1 = nlp(text1)
        doc2 = nlp(text2)

        # Use spaCy's built-in similarity if vectors are available
        if doc1.has_vector and doc2.has_vector:
            return doc1.similarity(doc2)
        else:
            # Fallback to token-based similarity if vectors are not present for docs
            tokens1 = set([token.lemma_.lower() for token in doc1 if not token.is_stop])
            tokens2 = set([token.lemma_.lower() for token in doc2 if not token.is_stop])

            if not tokens1 or not tokens2:
                return 0

            intersection = tokens1.intersection(tokens2)
            union = tokens1.union(tokens2)

            return len(intersection) / len(union) if union else 0

    def preprocess_text(self, text):
        """Clean and normalize text for better matching"""
        # First correct spelling
        corrected_text, _ = self.correct_spelling(text)
        text = corrected_text

        # Convert to lowercase
        text = text.lower().strip()
        # Remove extra spaces
        text = re.sub(r'\s+', ' ', text)
        # Remove punctuation except apostrophes
        text = re.sub(r'[^\w\s\']', '', text)
        return text

    def extract_keywords(self, text):
        """Extract relevant keywords from user input (fallback method)"""
        text = self.preprocess_text(text)
        found_keywords = []

        for category, keywords in self.keywords.items():
            for keyword in keywords:
                if keyword in text:
                    found_keywords.append(category)
                    break

        return found_keywords

    def calculate_similarity(self, text1, text2):
        """Calculate similarity between two texts using difflib (fallback method)"""
        return difflib.SequenceMatcher(None, text1, text2).ratio()

    def find_best_match(self, user_question):
        """Find the best matching answer using NLP and multiple techniques"""
        # Preprocess and correct the question
        user_question_clean = self.preprocess_text(user_question)
        
        # Classify intent
        intent = self.classify_intent(user_question_clean)

        # Extract entities and keywords
        entities = self.extract_entities(user_question)
        nlp_keywords = self.extract_keywords_nlp(user_question_clean)
        basic_keywords = self.extract_keywords(user_question_clean)

        # Combine all keywords
        all_keywords = list(set(nlp_keywords + basic_keywords))

        best_match = None
        best_score = 0

        for question, answer in self.qa_database.items():
            question_clean = self.preprocess_text(question)

            # 1. Exact substring matching (highest priority)
            if user_question_clean in question_clean or question_clean in user_question_clean:
                return answer

            # 2. Intent-based matching
            question_intent = self.classify_intent(question_clean)
            intent_score = 1.0 if intent == question_intent and intent != 'general' else 0

            # 3. Keyword-based matching (improved with NLP keywords)
            question_keywords = self.extract_keywords_nlp(question_clean)
            if not question_keywords:  # Fallback to basic keywords
                question_keywords = self.extract_keywords(question_clean)

            keyword_matches = len(set(all_keywords) & set(question_keywords))
            keyword_score = keyword_matches / max(len(all_keywords), 1) if all_keywords else 0

            # 4. Semantic similarity using spaCy
            semantic_score = self.semantic_similarity(user_question_clean, question_clean)

            # 5. Fuzzy string matching (fallback)
            fuzzy_score = self.calculate_similarity(user_question_clean, question_clean)

            # 6. Entity matching
            entity_score = 0
            if entities:
                question_entities = self.extract_entities(question)
                entity_texts = [e['text'].lower() for e in entities]
                question_entity_texts = [e['text'].lower() for e in question_entities]
                entity_matches = len(set(entity_texts) & set(question_entity_texts))
                entity_score = entity_matches / len(entity_texts) if entity_texts else 0

            # Combined scoring with improved weights
            if nlp and nlp.vocab.has_vector('test'):  # If spaCy is available and vectors are loaded, prioritize semantic similarity
                combined_score = (
                    intent_score * 0.3 +
                    semantic_score * 0.25 +
                    keyword_score * 0.2 +
                    entity_score * 0.15 +
                    fuzzy_score * 0.1
                )
            else:  # Fallback scoring without semantic similarity
                combined_score = (
                    intent_score * 0.35 +
                    keyword_score * 0.3 +
                    fuzzy_score * 0.25 +
                    entity_score * 0.1
                )

            if combined_score > best_score:
                best_score = combined_score
                best_match = answer

        # Return best match if score is above threshold
        if best_score > 0.25:
            return best_match
        else:
            return self.get_contextual_response(intent, all_keywords, entities)

    def get_contextual_response(self, intent, keywords, entities):
        """Provide contextual responses based on intent and extracted information"""
        responses = {
            'id_application': "For ID applications, you'll need your birth certificate, proof of residence, and supporting documents. Visit your nearest Home Affairs office or start online via eHomeAffairs. Processing takes 10-14 working days.",

            'passport_services': "For passport services, bring your current ID, completed DHA-73 form, passport photos (50mm x 35mm), and R400 fee. Processing takes 10-15 working days. You can track your application online.",

            'birth_certificate': "For birth certificates, apply at Home Affairs with hospital birth notification, parents' IDs, and witness statements if required. Processing usually takes 3-5 working days.",

            'death_certificate': "For death certificates, bring the medical certificate of death, deceased's ID, and proof of relationship. Apply at any Home Affairs office within 72 hours of death.",

            'marriage_services': "For marriage registration, visit Home Affairs within 3 months of your ceremony with your marriage certificate, both parties' IDs, and two witnesses. Foreign nationals may need additional documents.",

            'visa_immigration': "For visa applications, contact the nearest South African embassy/consulate with required documents including proof of funds, accommodation, and return tickets. Processing varies by visa type.",

            'citizenship': "For citizenship applications, you must meet residency requirements and demonstrate good character. Apply at Home Affairs with proof of residence, language proficiency, and supporting documents.",

            'lost_documents': "For lost/stolen documents, first report to police and get an affidavit. Then apply for replacement at Home Affairs with supporting documents and police report.",

            'appointments': "Book appointments online via eHomeAffairs portal, call 0800 60 11 90, or visit your nearest office directly. Online booking is recommended to avoid queues.",

            'contact_info': "Contact Home Affairs at 0800 60 11 90 (toll-free) or visit their official website. Offices are open Monday-Friday 8:00 AM to 3:30 PM, some offer Saturday services.",
        }

        if intent in responses:
            return responses[intent]
        else:
            # Generic response with helpful information
            return ("I'd be happy to help you with Home Affairs services. For specific assistance, please contact the Home Affairs hotline at 0800 60 11 90 or visit your nearest office. "
                                "Common services include ID applications, passports, birth certificates, and visa applications. What specific service do you need help with?")

    def get_default_response(self, keywords):
        """Provide contextual default responses based on keywords"""
        if 'id' in keywords:
            return "For ID-related queries, please visit your nearest Home Affairs office with your birth certificate and supporting documents. You can also call 0800 60 11 90 for more information."
        elif 'passport' in keywords:
            return "For passport services, you'll need your current ID, completed DHA-73 form, passport photos, and R400 fee. Processing takes 10-15 working days."
        elif 'visa' in keywords:
            return "For visa applications, please contact the nearest South African embassy or consulate in your country, or visit Home Affairs if you're already in South Africa."
        elif 'appointment' in keywords:
            return "You can book appointments online via eHomeAffairs, call 0800 60 11 90, or visit your nearest Home Affairs office directly."
        else:
            return "I apologize, but I don't have specific information about that. For detailed assistance, please contact Home Affairs at 0800 60 11 90 or visit your nearest Home Affairs office. Is there anything else about Home Affairs services I can help you with?"

    def get_response(self, user_message):
        """Main method to get chatbot response with enhanced NLP"""
        # Update stats
        self.stats['messages_processed'] += 1

        # Store original message
        original_message = user_message

        # Store in chat history
        self.chat_history.append({
            'user': user_message,
            'timestamp': datetime.now().isoformat(), # Use ISO format for better API consistency
            'type': 'user'
        })

        # Get bot response
        bot_response = self.find_best_match(user_message)

        # Add some context about spelling correction if significant changes were made
        corrected_message, _ = self.correct_spelling(user_message)
        spelling_note = None
        if corrected_message.lower() != user_message.lower():
            spelling_note = f"Note: I interpreted your question as: '{corrected_message}'"
            # bot_response += spelling_note # You might want to return this separately in API response

        self.chat_history.append({
            'bot': bot_response,
            'timestamp': datetime.now().isoformat(),
            'type': 'bot',
            'intent': self.classify_intent(user_message),
            'entities': self.extract_entities(user_message) if nlp else [],
            'corrected_input': corrected_message if corrected_message != user_message else None
        })

        return bot_response, spelling_note

    def analyze_conversation(self):
        """Analyze conversation patterns and extract insights"""
        if not self.chat_history:
            return {}

        user_messages = [msg for msg in self.chat_history if msg['type'] == 'user']
        bot_messages = [msg for msg in self.chat_history if msg['type'] == 'bot']

        # Intent analysis
        intents = [msg.get('intent', 'general') for msg in bot_messages if 'intent' in msg]
        intent_counts = Counter(intents)

        # Entity analysis
        all_entities = []
        for msg in bot_messages:
            if 'entities' in msg and msg['entities']:
                all_entities.extend([ent['text'] for ent in msg['entities']])

        entity_counts = Counter(all_entities)

        # Common spelling corrections
        corrections = [msg.get('corrected_input') for msg in bot_messages
                       if msg.get('corrected_input')]

        return {
            'total_messages': len(user_messages),
            'most_common_intents': dict(intent_counts.most_common(5)),
            'most_common_entities': dict(entity_counts.most_common(5)),
            'spelling_corrections_count': len(corrections),
            'average_response_time': '0.8 seconds'  # Placeholder
        }

    def get_stats(self):
        """Return current statistics"""
        return self.stats

# Initialize chatbot
chatbot = HomeAffairsChatbot()

# API Endpoints
API_BASE_PATH = '/api/v1'

@app.route(f'{API_BASE_PATH}/chat', methods=['POST'])
def chat_api():
    """Handle chat messages via API"""
    try:
        data = request.get_json()
        user_message = data.get('message', '').strip()

        if not user_message:
            return jsonify({'error': 'Empty message'}), 400

        # Get bot response and spelling note
        bot_response, spelling_note = chatbot.get_response(user_message)

        response_data = {
            'response': bot_response,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'), # More standard timestamp
            'stats': chatbot.get_stats()
        }
        if spelling_note:
            response_data['spelling_note'] = spelling_note

        return jsonify(response_data), 200

    except Exception as e:
        app.logger.error(f"Error in /api/v1/chat: {e}")
        return jsonify({'error': 'Internal server error', 'details': str(e)}), 500

@app.route(f'{API_BASE_PATH}/stats', methods=['GET'])
def get_stats_api():
    """Get current statistics"""
    try:
        return jsonify(chatbot.get_stats()), 200
    except Exception as e:
        app.logger.error(f"Error in /api/v1/stats: {e}")
        return jsonify({'error': 'Internal server error', 'details': str(e)}), 500

@app.route(f'{API_BASE_PATH}/history', methods=['GET'])
def get_history_api():
    """Get chat history"""
    try:
        # Return last 50 messages, ensuring timestamps are strings
        history = []
        for msg in chatbot.chat_history[-50:]:
            formatted_msg = msg.copy()
            if isinstance(formatted_msg.get('timestamp'), datetime):
                formatted_msg['timestamp'] = formatted_msg['timestamp'].isoformat()
            history.append(formatted_msg)
        return jsonify(history), 200
    except Exception as e:
        app.logger.error(f"Error in /api/v1/history: {e}")
        return jsonify({'error': 'Internal server error', 'details': str(e)}), 500

@app.route(f'{API_BASE_PATH}/reset', methods=['POST'])
def reset_chat_api():
    """Reset chat history"""
    try:
        chatbot.chat_history = []
        return jsonify({'status': 'Chat history reset successfully'}), 200
    except Exception as e:
        app.logger.error(f"Error in /api/v1/reset: {e}")
        return jsonify({'error': 'Internal server error', 'details': str(e)}), 500

@app.route(f'{API_BASE_PATH}/analyze', methods=['GET'])
def analyze_conversation_api():
    """Get conversation analysis"""
    try:
        analysis = chatbot.analyze_conversation()
        return jsonify(analysis), 200
    except Exception as e:
        app.logger.error(f"Error in /api/v1/analyze: {e}")
        return jsonify({'error': 'Internal server error', 'details': str(e)}), 500

@app.route(f'{API_BASE_PATH}/correct_spelling', methods=['POST'])
def correct_spelling_api():
    """Endpoint to correct spelling of text"""
    try:
        data = request.get_json()
        text = data.get('text', '')

        if not text:
            return jsonify({'error': 'No text provided'}), 400

        corrected_text, individual_corrections = chatbot.correct_spelling(text)

        response_data = {
            'original_text': text,
            'corrected_text': corrected_text,
            'corrections_applied': individual_corrections
        }
        return jsonify(response_data), 200

    except Exception as e:
        app.logger.error(f"Error in /api/v1/correct_spelling: {e}")
        return jsonify({'error': 'Internal server error', 'details': str(e)}), 500

if __name__ == '__main__':
    # For production, use a WSGI server like Gunicorn
    # For development, you can run: python your_api_file.py
    app.run(debug=True, host='0.0.0.0', port=5000)