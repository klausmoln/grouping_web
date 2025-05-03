from flask import Flask, render_template, request, jsonify
import json
import os
import random
import time

app = Flask(__name__)

DATA_FILE = "data/people.json"
LAST_GROUP_FILE = "data/last_groups.json"

class Person:
    def __init__(self, name, gender, location, spouse=None):
        self.name = name
        self.gender = gender
        self.location = location
        self.spouse = spouse

    def to_dict(self):
        return {
            "name": self.name,
            "gender": self.gender,
            "location": self.location,
            "spouse": self.spouse
        }

def load_people():
    if not os.path.exists(DATA_FILE):
        return [], []
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
        people = [Person(**p) for p in data.get("participating", [])]
        not_participating = [Person(**p) for p in data.get("not_participating", [])]
        return people, not_participating

def save_people(people, not_participating):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump({
            "participating": [p.to_dict() for p in people],
            "not_participating": [p.to_dict() for p in not_participating]
        }, f, ensure_ascii=False, indent=4)

def save_last_groups(groups):
    with open(LAST_GROUP_FILE, "w", encoding="utf-8") as f:
        json.dump([[p.name for p in group] for group in groups], f, ensure_ascii=False, indent=4)

def load_last_groups():
    if os.path.exists(LAST_GROUP_FILE):
        with open(LAST_GROUP_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def find_person(name, people, not_participating):
    for p in people:
        if p.name == name:
            return p
    for p in not_participating:
        if p.name == name:
            return p
    return None

def create_groups(people, num_groups):
    male_list = [p for p in people if p.gender == 'M']
    female_list = [p for p in people if p.gender == 'F']
    last_groups = load_last_groups()
    last_group_map = {name: set(p for p in group if p != name) for group in last_groups for name in group}
    spouse_map = {p.name: p.spouse for p in people if p.spouse}
    max_two_in_group = ["羽菲", "朱睿", "祖盈", "云翼", "彦文"]
    cannot_be_together = ["志冬", "常健", "李尧"]

    start = time.time()
    while True:
        random.shuffle(male_list)
        random.shuffle(female_list)
        groups = [[] for _ in range(num_groups)]

        i = -1
        for i, person in enumerate(male_list):
            groups[i % num_groups].append(person)
        i += 1
        for j, person in enumerate(female_list):
            groups[(i + j) % num_groups].append(person)

        valid = True
        group_sizes = [len(g) for g in groups]
        male_counts = [sum(1 for p in g if p.gender == 'M') for g in groups]
        female_counts = [sum(1 for p in g if p.gender == 'F') for g in groups]

        if max(group_sizes) - min(group_sizes) > 1 or \
           max(male_counts) - min(male_counts) > 1 or \
           max(female_counts) - min(female_counts) > 1:
            valid = False
        else:
            for group in groups:
                group_names = [p.name for p in group]
                for name in group_names:
                    if name in spouse_map and spouse_map[name] in group_names:
                        valid = False
                        break
                if not valid:
                    break
                for p in group:
                    if p.name in last_group_map:
                        overlap = last_group_map[p.name].intersection(set(x.name for x in group))
                        if len(overlap) >= 3:
                            valid = False
                            break
                if not valid:
                    break
                count_max_two = sum(1 for name in group_names if name in max_two_in_group)
                if count_max_two > 2:
                    valid = False
                    break
                count_cannot_together = sum(1 for name in group_names if name in cannot_be_together)
                if count_cannot_together >= 2:
                    valid = False
                    break

        if valid:
            save_last_groups(groups)
            return groups
        if time.time() - start > 0.5:
            return []

@app.route("/")
def index():
    people, not_participating = load_people()
    return render_template("index.html", people=people, not_participating=not_participating)

@app.route("/add", methods=["POST"])
def add_person():
    name = request.form.get("name")
    gender = request.form.get("gender")
    location = request.form.get("location")
    spouse = request.form.get("spouse")

    person = Person(name, gender, location, spouse)
    people, not_participating = load_people()
    people.append(person)
    save_people(people, not_participating)
    return jsonify({"success": True})

@app.route("/withdraw", methods=["POST"])
def withdraw_person():
    name = request.form.get("name")
    people, not_participating = load_people()
    person = next((p for p in people if p.name == name), None)
    if person:
        people.remove(person)
        not_participating.append(person)
        save_people(people, not_participating)
    return jsonify({"success": True})

@app.route("/join", methods=["POST"])
def join_person():
    name = request.form.get("name")
    people, not_participating = load_people()
    person = next((p for p in not_participating if p.name == name), None)
    if person:
        not_participating.remove(person)
        people.append(person)
        save_people(people, not_participating)
    return jsonify({"success": True})

@app.route("/to_onsite", methods=["POST"])
def to_onsite():
    name = request.form.get("name")
    people, not_participating = load_people()
    person = find_person(name, people, not_participating)
    if person:
        person.location = "On-site"
        save_people(people, not_participating)
        return jsonify({"success": True})
    return jsonify({"error": "Person not found"}), 404

@app.route("/to_online", methods=["POST"])
def to_online():
    name = request.form.get("name")
    people, not_participating = load_people()
    person = find_person(name, people, not_participating)
    if person:
        person.location = "Online"
        save_people(people, not_participating)
        return jsonify({"success": True})
    return jsonify({"error": "Person not found"}), 404

@app.route("/group", methods=["POST"])
def group_people():
    num_groups = int(request.form.get("num_groups"))
    people, _ = load_people()
    if len(people) < num_groups:
        return jsonify({"error": "人数不足，无法分组。"})
    groups = create_groups(people, num_groups)
    if not groups:
        return jsonify({"error": "没有找到满足条件的分组方案。"})
    grouped = [[p.to_dict() for p in g] for g in groups]
    return jsonify({"groups": grouped})

if __name__ == "__main__":
    os.makedirs("data", exist_ok=True)
    app.run(debug=True)