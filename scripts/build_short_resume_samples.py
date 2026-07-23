#!/usr/bin/env python3
"""Build short, resume-like PDF samples from the controlled candidate set."""

from pathlib import Path

from generate_test_pdfs import render


ROOT = Path(__file__).resolve().parents[1]
SAMPLE_ROOT = ROOT / "test_data" / "github_fixture_samples"
SOURCE_DIR = SAMPLE_ROOT / "resume_sources"
RESUME_DIR = SAMPLE_ROOT / "resumes"


SHORT_RESUMES = {
    "short_candidate_01": """# Short Candidate 01
fixture-candidate-01@example.test | Minsk, BY | Remote
GitHub: https://github.com/fixture-candidate-01
Portfolio: https://example.test/portfolio

## Target Role
Junior Front-end / Vue.js Developer

## Summary
Junior web developer with 1.5 years of experience building responsive pages and small Vue.js projects. Comfortable with JavaScript, HTML, CSS, Git, npm, and basic Scrum workflows.

## Work Experience
Synergy Group | Junior Front-end Developer | 2018-06 - 2018-09
- Built responsive landing pages and SPA layouts from design specifications.
- Used Pug, PostCSS, Gulp, BEM, grids, and Git in a Scrum process.
- Coordinated with designers and estimated front-end sprint tasks.

Freelance | Front-end Developer | 2018-10 - 2019-12
- Delivered small portfolio and landing-page sites for clients.
- Customized jQuery plugins and implemented mobile-first CSS layouts.

## Projects
Powerdime | https://example.test/portfolio
- Main commercial layout project with index, purchase, and wallet pages.
- Technologies: HTML, CSS, JavaScript, Pug, PostCSS, Gulp.

Vue Portfolio | https://github.com/fixture-candidate-01/vue-portfolio
- Personal Vue.js showcase project for front-end components and layouts.

## Technical Skills
Programming languages: JavaScript, HTML, CSS.
Frameworks and libraries: Vue.js 2, Bootstrap, jQuery.
Developer tools: Git, npm, yarn, Gulp, Webpack.
Practices: responsive design, mobile-first CSS, Scrum, BEM.

## Education
Self-directed front-end training | 2017 - 2018
- Focused on HTML, CSS, JavaScript, Git, and responsive UI development.

## Awards
No formal awards listed.
""",
    "short_candidate_02": """# Short Candidate 02
fixture-candidate-02@example.test | Remote
GitHub: https://github.com/fixture-candidate-02

## Target Role
Junior .NET Developer

## Summary
Entry-level backend developer with academic and personal projects in C Sharp, DotNET, WPF, Windows Forms, SQL, and file-processing utilities. No full-time production experience yet, but comfortable building small desktop tools and learning new APIs.

## Work Experience
Academic Projects | Student Developer | 2019-01 - 2020-06
- Built course projects using C Sharp, DotNET Framework, LINQ, ADO.NET, and SQL.
- Practiced object-oriented design, UML, version control, and basic testing.

## Projects
Flashdrive Watcher | https://github.com/fixture-candidate-02/flashdrive-watcher
- Desktop utility that watches for USB devices and synchronizes selected folders.
- Technologies: C Sharp, WPF, ADO.NET, LINQ, async tasks.

Base64 Toolkit | https://github.com/fixture-candidate-02/base64-toolkit
- Small file encoding and decoding utility.

Cryptography Demo | https://github.com/fixture-candidate-02/cryptography-demo
- Demonstration project for XOR, RC4, Base64, and Huffman-style compression.

## Skills
Programming languages: C Sharp, C Plus Plus, SQL, JavaScript basics.
Frameworks and libraries: DotNET Framework, WPF, Windows Forms, ASP.NET MVC.
Data access: LINQ, ADO.NET, Entity Framework, SQL Server.
Developer tools: Visual Studio, ReSharper, Git, SourceTree.

## Education
Computer science coursework | 2018 - 2020
- Studied programming fundamentals, databases, object-oriented design, and algorithm analysis.

## Awards
No formal awards listed.
""",
    "short_candidate_03": """# Short Candidate 03
fixture-candidate-03@example.test | Remote
GitHub: https://github.com/fixture-candidate-03
Portfolio: https://example.test/portfolio

## Target Role
Java Developer

## Summary
Java developer with about 1.5 years of outstaff and freelance experience. Built backend services and APIs using Spring, Hibernate, SQL databases, REST, Git, and unit testing. Also has basic front-end experience with HTML, CSS, and AngularJS.

## Work Experience
Outstaff and Freelance Clients | Java Developer | 2019-03 - 2020-10
- Developed Java backend features for foreign client projects.
- Implemented REST APIs, database access layers, and service integrations.
- Used Git, unit tests, and issue-based development workflows.

## Projects
Happ Service | https://github.com/fixture-candidate-03/happ-service
- Spring-based backend service with REST endpoints and database persistence.

Cardiff API | https://github.com/fixture-candidate-03/cardiff-api
- API prototype using Java, Spring MVC, and SQL storage.

Queue Dump | https://github.com/fixture-candidate-03/queue-dump
- Utility project for queue processing and debugging.

## Skills
Backend: Java, Spring Core, Spring MVC, Spring Data, Spring Security, Hibernate, JPA, REST.
Databases: SQL, MySQL, PostgreSQL, MongoDB.
Testing: JUnit, EasyMock, Spring Test.
Front-end: HTML5, CSS, AngularJS.
Tools: Git, JSON, OpenShift.

## Education
Java backend self-study and professional training | 2018 - 2019
- Focused on Spring, database design, REST APIs, and automated tests.

## Awards
No formal awards listed.
""",
    "short_candidate_04": """# Short Candidate 04
fixture-candidate-04@example.test | Remote
GitHub: https://github.com/fixture-candidate-04
Portfolio: https://example.test/portfolio

## Target Role
Android Developer

## Summary
Android developer with 7 years of experience building mobile applications, research prototypes, and hackathon projects. Strong in Android SDK, Java, databases, Python, C/C++, JavaScript, and product-oriented mobile development. Has published apps and several GitHub projects.

## Work Experience
Mobile Product Teams | Android Developer | 2016-01 - Present
- Built and maintained Android applications from prototype to release.
- Integrated local databases, network APIs, and device capabilities.
- Worked on research prototypes, hackathon projects, and production mobile features.

Independent Developer | Mobile Engineer | 2014-06 - 2015-12
- Built Android side projects and published small apps to a public app store.
- Explored game simulation, local networking, and offline-first mobile workflows.

## Projects
Mesh Network Chat | https://github.com/fixture-candidate-04/mesh-network-chat
- Offline-first Android chat prototype using local networking concepts.

Space Simulator | https://github.com/fixture-candidate-04/diaphragm-view
- Mobile simulation project with AI-driven behavior.

Checkable Items | https://github.com/fixture-candidate-04/checkable-items
- Android sample app for list interaction and local persistence.

## Skills
Mobile: Android SDK, Java, SQLite, local storage, Google APIs, mobile UI.
Programming: Python, C, C++, JavaScript.
Engineering: Databases, API integration, offline-first design, prototyping, release workflows.

## Education
Bachelor of Computer Science | Technical University | 2010 - 2014
- Studied software engineering, databases, algorithms, and mobile application development.

## Awards
Hackathon and research project participation listed in portfolio.
""",
}


def main() -> None:
    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    RESUME_DIR.mkdir(parents=True, exist_ok=True)

    for name, content in SHORT_RESUMES.items():
        source = SOURCE_DIR / f"{name}.txt"
        output = RESUME_DIR / f"{name}.pdf"
        source.write_text(content, encoding="utf-8")
        render(source, output)
        print(f"generated {output.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
