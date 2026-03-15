## Task 4 prompt

I used AI to review my architecture after learning the basics of RabbitMQ and system design. I specifically asked for help validating the diagram structure, identifying missing components, and improving the explanation for the README.

## Task 3 prompt
Help me build a clean Python automation script for this DOM scraping task. The script should:
- open the target page in a real browser
- scrape all image elements and save them as base64 in allimages.json
- scrape only human-visible images and save them in visible_images_only.json
- scrape visible text instructions and save them to a text file

Please organize the code into clear functions and explain the purpose of each part so I can review and understand it.


## Task 1 
AI assistance was used during development to help structure parts of the implementation and improve code organization. The final solution was reviewed, tested, and run locally before submission.

The prompt : Help me build a clean Python automation script for : Automation - Stealth Assessment
* Using python playwright, Go to link __https://cd.captchaaiplus.com/turnstile.html__
* Ensure to get verified (success!) for the captcha (turnstile) click submit and get the success final message and print the turnstile token
   1. Do in playwright headless (true and false)
* Retry 10 times for the same process and get the final success rate (at least 60%) 
   1. Screen record a video of ten attempts with the required success rate

   what topics should I know ?