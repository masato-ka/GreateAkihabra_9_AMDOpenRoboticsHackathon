**### Make a fork or copy of this repo and fill in your team submission details! ###**

# AMD_Robotics_Hackathon_2025_[Automated donuts order assistant]

## Team Information

**Team:** No.9 Greate Akihabara (Masato Kawamura, Kazuki Murata, Fujima Yuji, Shota Yoshikai)

**Summary:** We worked on automating takeout at a doughnut shop. After receiving orders from customers, robots controlled by VLA pack the ordered doughnuts.

*[This is final result VIDEO this Application NO9GreateAkihabara_AMDHackathon.mp4](https://resv2.craft.do/user/full/7e1bcac5-12e5-0648-9cd4-f316c4cdd8bc/doc/D6497AC6-3DF3-436B-84D3-3F6B771F9A4E/7E75AB0C-EB86-43A5-8501-C2BFEC25DB00_2/BSUnWVPreEv8dfxNLgypMB6Oqe3qYJVzfdRl3mhMUKsz/NO9GreateAkihabara_AMDHackathon.mp4)
[GreatAkihabara Donuts.mp4](https://resv2.craft.do/user/full/7e1bcac5-12e5-0648-9cd4-f316c4cdd8bc/doc/D6497AC6-3DF3-436B-84D3-3F6B771F9A4E/BFD5AE59-2237-4F04-893B-1452D9353366_2/0luGK5NWro8kToo0Pxa3ITN3BEraA0NAxscBztTlcEYz/GreatAkihabara%20Donuts.mp4)
## Submission Details

### 1. Mission Description
- *We worked on automating takeout at a doughnut shop. After receiving orders from customers, robots controlled by VLA pack the ordered doughnuts.*

### 2. Creativity
- *Mobile shops connect directly to the VLA, where robots prepare goods based on customer orders. Mobile ordering encourages increased customer orders, but this growth also places a burden on stores. This system reduces that burden for the store while enabling swift delivery of goods to customers.*
- To achieve this goal, we employed the VLA model. We also attempted to resolve the following issues where the VLA model poses challenges in real-world use cases.
  - **Long-Horizon Task:** Real-world tasks are not short tasks like block pick-and-place, but rather long-term tasks consisting of a series of interconnected subtasks. Training VLA on long-term tasks is difficult.
  - **Dual-Arm:** Placing donuts into a box or closing the lid cannot be achieved with a single arm. It requires the coordinated movement of two arms, such as passing objects between them and moving in sync.
  - **Recognition End of Task:** The VLA cannot recognize that it has completed a task on its own. Therefore, it is necessary to systematically control the completion of VLA tasks.

### 3. Technical implementations
- *Teleoperation / Dataset capture*
  - We are performing teleoperation of intricate tasks using a dual-arm manipulator. The dataset used for training consists of 120 EP, but including failures and retries, we have acquired over 180 EP of data.
  - It performs actions such as passing donuts using dual-arm manipulators, opening boxes, locking boxes, and ringing bells.
     - [Pick up donuts](https://resv2.craft.do/user/full/7e1bcac5-12e5-0648-9cd4-f316c4cdd8bc/doc/D6497AC6-3DF3-436B-84D3-3F6B771F9A4E/ADFE75F0-C42E-4176-80D4-CC29AEFA9307_2/pUvOxaxDOYAxiJ7DcNxN0FrKy20fqP2bcSXvBLE0kxwz/%202025-12-07%2014.41.47.mov)
     - [Close the box](https://resv2.craft.do/user/full/7e1bcac5-12e5-0648-9cd4-f316c4cdd8bc/doc/D6497AC6-3DF3-436B-84D3-3F6B771F9A4E/B3EF1A71-5A69-44EE-82DD-43EC14A9FE47_2/9lyLQG0MTC6gfZ9jwtYLTYzmhoyasEXyaIhiJEp0Fi8z/%202025-12-07%2014.43.23.mov)
- 
- *Training*
  - We using SmolVLA to reduce inference cost.
  - We effectively utilized two MI300X units. We are training the model while verifying its performance by changing multiple datasets and settings (batch size/steps).
  - The product preparation process involves setting up **long-horizon tasks.** Therefore, we trained the model to learn these tasks by breaking them down into the following three tasks:
    - Place chocolate donuts into the box
    - Place strawberry donuts into the box
    - Close the box lid
  - However, since the action was actually incomplete, the action of closing the box lid was trained as a separate model.
  - 
- *Inference*
   - The boxes and donuts used this time change shape while being manipulated by the robot. It is necessary to respond appropriately to these changes. 
   - Generally, VLA systems employing Action Chunking are vulnerable to such dynamic environmental changes.
   - Therefore, we adopted Real-Time Action Chunking, as used in LeRobot, for inference.
   - This approach is effective for ensuring smooth motion and adapting to environmental changes.
   - The VLA cannot determine when its own tasks are complete. The robot notifies the system that a task has ended by ringing a bell at the conclusion of each task. The bell is connected to the system via USB, and ringing it sends a notification to the system.
     - *<Image/video of inference eval>*

### The System Architecture
This system consists of an Order Chatbot, a Physical System, and a message queue connecting them.
1. **Order Chatbot**
   The Order Chatbot allows customers to place donut orders interactively. The system can notify customers of two states: order acceptance and order preparation completion.
2  **Physical System**
   Based on instructions received from the Order Chatbot via the message queue, it performs donut packing.
   - **State Management**
      State Management handles the robot's task execution. It passes task interactions to the VLA/IL for execution based on instructions from the message queue. It manages task execution status and notifies the Order Chatbot of the state.
   - **VLA/IL**
      Composed of the robot's task policy and the program executing it. It controls the robot and executes tasks based on the input text instructions and the environmental state.
   - **Bell**
     Connected to the state controller, it notifies the system of task completion when struck by the robot. In other words, the robot manages its own tasks!

   ![Image.png](https://resv2.craft.do/user/full/7e1bcac5-12e5-0648-9cd4-f316c4cdd8bc/doc/D6497AC6-3DF3-436B-84D3-3F6B771F9A4E/35D8F616-E47E-497A-98AD-C7E76C517FE1_2/2bBTCxvRoAZOffRKJtft5Tpz04Pw8KXpxmrSQPyFfyEz/Image.png)





### 4. Ease of use
- The robot can handle three tasks: picking up chocolate and strawberry donuts, and closing the lid.

## Additional Links
*For example, you can provide links to:*

- *Link to a video of your robot performing the task*
- *URL of your dataset in Hugging Face*
  - *[LINK to donuts pick up](https://huggingface.co/datasets/masato-ka/donuts-shop-dataset-v0)*
  - *[LINK to close box](masato-ka/donuts-shop-close-box-dataset-v0)*
- *URL of your model in Hugging Face*
  - *[LINK to donuts pick up model](https://huggingface.co/masato-ka/smolvla-donuts-shop-v1)*
  - *[LINK to close box model](masato-ka/smolvla-donuts-shop-close-box-v0)*
- *Link to a blog post describing your work*

